#!/usr/bin/env python3
"""하이브리드 relay: MinerU 출력(텍스트 HTML)을 이미지 대신 LLM에 넣어 골격 복원.

가설: 파서가 OCR/지각을 처리하면(빈칸 병목 제거), LLM이 그 텍스트에서 더 정확한 골격을 만들까?
입력 = mineru/mineru_s6_raw.html (MinerU2.5-Pro의 s6 평탄 9열 출력).
과제 = 빈 셀 골격 복원(표 밖 문단 제외·중첩 유지·빈칸 별도 셀). 채점 = TEDS-Struct vs 중첩 GT.
모델: gemini-3.1-pro(네이티브, thinking low) / claude-opus-4.8(OpenRouter, +think6k).
사용: ../../../.venv/bin/python run_relay.py <model_id> [tag]
"""
import base64  # noqa: F401  (claude 경로 텍스트만 — 호환 위해 유지)
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize
from teds import teds_struct_html

_pos = [a for a in sys.argv[1:] if not a.startswith("--")]
WITH_IMAGE = "--with-image" in sys.argv
MODEL = _pos[0] if _pos else "gemini-3.1-pro-preview"
TAG = _pos[1] if len(_pos) > 1 else MODEL.split("/")[-1].replace("-preview", "")
IS_CLAUDE = MODEL.startswith("anthropic/")
GT = (SYN / "gt" / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
MINERU_IN = (HERE / "mineru" / "mineru_s6_raw.html").read_text(encoding="utf-8")
PNGP = SYN / "png" / "s6-p011clone.png"

SYSTEM = """너는 표의 '구조 골격'을 복원하는 정밀 도구다.
빈 셀 HTML(table/tr/td + colspan/rowspan + 중첩표)만 출력한다. 설명·코드펜스 없이 <table>...</table> 만."""

_RULES = """규칙:
- 모든 셀은 빈 <td></td>. 비어 있는 칸도 각각 별도의 셀로 센다.
- 보이는 병합만 colspan/rowspan으로. 셀 안의 표는 중첩 <table>로 유지(깊이 제한 없음).
- 표 바깥/아래의 문단 글(절차 설명·비고 등)은 표의 행이 아니다 — 표에 포함하지 마라.
- <table>...</table> 만 출력."""

if WITH_IMAGE:
    TASK = f"""첨부한 이미지에 표가 있다. 이 표의 '구조 골격'을 빈 셀 HTML로 복원하라.
구조(행·열·병합·중첩) 판단은 **이미지를 기준**으로 하되, 아래 'OCR 파서 참고 HTML'(평탄화·오류 가능)은
셀 내용·텍스트 식별을 돕는 **참고용**으로만 쓰라(구조를 그대로 베끼지 말 것).

{_RULES}

[OCR 파서 참고 HTML]
{MINERU_IN}"""
else:
    TASK = f"""아래는 한 문서 표를 다른 도구(OCR 파서)가 추출한 HTML이다(평탄화·오류가 있을 수 있음).
이 표의 '구조 골격'을 빈 셀 HTML로 복원하라.

{_RULES}

[표 HTML]
{MINERU_IN}"""


def key(name):
    import os
    if os.environ.get(name):
        return os.environ[name]
    for line in (SYN.parents[1] / ".env" / ".env").read_text().splitlines():
        if line.strip().startswith(name) and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit(f"{name} 못 찾음")


def call_gemini():
    from google import genai
    from google.genai import types
    c = genai.Client(api_key=key("GEMINI_API_KEY"))
    parts = []
    cfg = dict(system_instruction=SYSTEM, temperature=1.0, max_output_tokens=16000,
               thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW))
    if WITH_IMAGE:
        parts.append(types.Part.from_bytes(data=PNGP.read_bytes(), mime_type="image/png"))
        cfg["media_resolution"] = types.MediaResolution.MEDIA_RESOLUTION_HIGH
    parts.append(types.Part.from_text(text=TASK))
    r = c.models.generate_content(
        model=MODEL, contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(**cfg))
    return r.text or "", r.usage_metadata.total_token_count


def call_claude():
    if WITH_IMAGE:
        b = base64.b64encode(PNGP.read_bytes()).decode()
        user = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}},
                {"type": "text", "text": TASK}]
    else:
        user = TASK
    payload = {"model": MODEL, "temperature": 1.0, "max_tokens": 16000,
               "reasoning": {"max_tokens": 6000},
               "messages": [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": user}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {key('OPENROUTER_API_KEY')}",
                                          "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=400) as resp:
                d = json.load(resp)
                return d["choices"][0]["message"].get("content") or "", d.get("usage", {}).get("total_tokens")
        except urllib.error.HTTPError as e:
            msg = f"{e.code} {e.read().decode()[:160]}"
            if attempt < 3 and any(t in msg for t in ("429", "500", "502", "503", "Overloaded")):
                time.sleep(10 * (attempt + 1)); continue
            sys.exit(f"오류: {msg}")


def main():
    raw, tok = (call_claude() if IS_CLAUDE else call_gemini())
    m = re.search(r"<table.*</table>", raw, re.S | re.I)
    skel = skeletonize(m.group(0)) if m else ""
    teds = round(teds_struct_html(skel, GT), 5) if skel else None
    inp = "이미지 + MinerU 참고HTML" if WITH_IMAGE else "MinerU2.5-Pro output (text)"
    folder = "img-plus-mineru" if WITH_IMAGE else "mineru-relay"
    rec = {"model": MODEL, "page": "s6-p011clone", "input": inp,
           "teds_struct": teds, "skeleton": skel, "raw": raw, "total_tokens": tok,
           "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    out = HERE / folder / f"{TAG}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {folder}/{TAG}.json  TEDS={teds}  ({tok}tok)")
    print("--- skeleton ---"); print(skel)


if __name__ == "__main__":
    main()
