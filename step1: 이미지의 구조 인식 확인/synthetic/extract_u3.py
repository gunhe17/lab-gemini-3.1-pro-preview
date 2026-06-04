#!/usr/bin/env python3
"""U3 — 완전 콘텐츠 변환(이미지 → 온전한 HTML + Markdown). 모델별 튜닝 프롬프트.

u1(빈 골격)/u2(지각)를 넘어, VLM의 텍스트·관계 강점으로 '내용까지' 변환.
프롬프트는 각 모델 가이드대로 분리:
  - Gemini: docs/prompt.md (XML 구조·이미지 먼저·출력형식 명시·"충분히 보고")
  - Claude: docs/claude-prompting.md (역할·맥락·<example> few-shot·긍정형 규칙·<self_check>)
백엔드 자동분기: anthropic/* → OpenRouter, 그 외 → 네이티브 Gemini.
채점: 구조=TEDS-Struct vs gt골격 / 콘텐츠=텍스트 시퀀스 유사도 vs 소스 HTML.
사용: ../../.venv/bin/python extract_u3.py <model_id> [tag]
"""
import base64
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE  # synthetic 최상위로 이동됨
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize
from teds import teds_struct_html

PAGE = "s6-p011clone"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3-flash-preview"
TAG = sys.argv[2] if len(sys.argv) > 2 else MODEL.split("/")[-1].replace("-preview", "")
IS_CLAUDE = MODEL.startswith("anthropic/")
PNGP = SYN / "png" / f"{PAGE}.png"
GT_SKEL = (SYN / "gt" / f"{PAGE}.skeleton.html").read_text(encoding="utf-8")
GT_SRC = (SYN / "html" / f"{PAGE}.html").read_text(encoding="utf-8")

# ── Gemini 튜닝 프롬프트 (docs/prompt.md) ─────────────────────────────────────
SYS_G = """<role>너는 문서 이미지의 표를 내용까지 완전하게 옮기는 변환 도구다. 텍스트·관계 전사가 핵심이다.</role>
<rules>
- 모든 셀의 텍스트를 빠짐없이 전사한다(불릿·번호·기호 포함).
- 병합은 colspan/rowspan으로, 셀 안의 표는 중첩 <table>로 보존한다.
- 표 바깥/아래의 문단 글은 표의 행이 아니다 — 표 밖 텍스트로 둔다.
</rules>
<output_format>먼저 <html>…완전한 <table>…</html>, 다음 <markdown>…동일 내용…</markdown>. 설명·코드펜스 없이 이 둘만.</output_format>"""
TASK_G = """<task>첨부 이미지의 표를 HTML과 Markdown 두 형식으로, 내용까지 완전히 변환하라.</task>
<final_instruction>이미지를 충분히 살펴본 뒤 위 출력 형식 그대로 출력하라.</final_instruction>"""

# ── Claude 튜닝 프롬프트 (docs/claude-prompting.md) ───────────────────────────
SYS_C = """<role>너는 문서 이미지의 표를 내용까지 완전하게 옮기는 변환 도구다.</role>
<rules>
- 모든 셀의 텍스트를 빠짐없이 전사한다(불릿·번호·기호 포함).
- 병합은 colspan/rowspan으로, 셀 안의 표는 중첩 <table>로 보존한다.
- 표 바깥/아래의 문단 글은 표의 행으로 넣지 않는다 — <table> 뒤에 별도 텍스트로 둔다.
- 비어 있는 칸도 각각 별도의 <td></td> 로 둔다.
</rules>
<output_format><html>…</html> 다음 <markdown>…</markdown> 만. 설명·코드펜스 없이.</output_format>"""
TASK_C = """<context>이 변환은 다운스트림이 문서를 재구성하는 데 쓰인다. 텍스트 누락·구조 왜곡·표 밖 문단의 표행 흡수가 없어야 한다.</context>

<example>
설명: [항목|값] 2열 표. 본문 왼쪽 칸은 비어 있고, 오른쪽 칸 안에 [구분|수치] 2열 표가 있다. 표 아래 "비고: 분기별 갱신." 문단.
<html>
<table>
  <tr><td>항목</td><td>값</td></tr>
  <tr><td></td><td><table><tr><td>구분</td><td>수치</td></tr></table></td></tr>
</table>
<p>비고: 분기별 갱신.</p>
</html>
<markdown>
| 항목 | 값 |
| --- | --- |
|  | 구분 / 수치 |

비고: 분기별 갱신.
</markdown>
(빈 칸도 별도 <td> · 셀 안 표는 중첩 · "비고:" 문단은 표 밖)
</example>

<task>첨부 이미지의 표를 위 예시와 같은 형식으로, 내용까지 완전히 변환하라.</task>

<self_check>출력 전: (1) 모든 텍스트를 전사했는가? (2) 표 밖 문단을 표 행에 넣지 않았는가? (3) 셀 안 표를 중첩으로, 빈 칸을 별도 셀로 유지했는가?</self_check>

점검 후 <html>…</html> 와 <markdown>…</markdown> 만 출력하라."""

SYSTEM, TASK = (SYS_C, TASK_C) if IS_CLAUDE else (SYS_G, TASK_G)


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
    r = c.models.generate_content(
        model=MODEL, contents=[types.Content(role="user", parts=[
            types.Part.from_bytes(data=PNGP.read_bytes(), mime_type="image/png"),
            types.Part.from_text(text=TASK)])],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM, temperature=1.0, max_output_tokens=16000,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)))
    return r.text or "", r.usage_metadata.total_token_count


def call_claude():
    b = base64.b64encode(PNGP.read_bytes()).decode()
    payload = {"model": MODEL, "temperature": 1.0, "max_tokens": 16000,
               "reasoning": {"max_tokens": 6000},
               "messages": [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}},
                                {"type": "text", "text": TASK}]}]}
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


def vis_text(html):
    t = re.sub(r"<style.*?</style>|<head.*?</head>|<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", "", t)


def main():
    raw, tok = (call_claude() if IS_CLAUDE else call_gemini())
    mh = re.search(r"<html>(.*?)</html>", raw, re.S | re.I)
    html = mh.group(1).strip() if mh else ((re.search(r"<table.*</table>", raw, re.S | re.I) or [None, raw])[0] or raw)
    mm = re.search(r"<markdown>(.*?)</markdown>", raw, re.S | re.I)
    md = mm.group(1).strip() if mm else ""
    mt = re.search(r"<table.*</table>", html, re.S | re.I)
    struct_teds = round(teds_struct_html(skeletonize(mt.group(0)), GT_SKEL), 5) if mt else None
    content_sim = round(difflib.SequenceMatcher(None, vis_text(GT_SRC), vis_text(html)).ratio(), 4)

    rec = {"model": MODEL, "page": PAGE, "prompt": "claude-tuned" if IS_CLAUDE else "gemini-tuned",
           "struct_teds": struct_teds, "content_sim": content_sim,
           "html": html, "markdown": md, "raw": raw, "total_tokens": tok,
           "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    out = HERE / "u3" / f"{TAG}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ u3/{TAG}.json  [{rec['prompt']}]  struct_teds={struct_teds} · content_sim={content_sim} · "
          f"html {len(html)}자 · md {len(md)}자 · {tok}tok")
    print("--- HTML 앞 500자 ---"); print(html[:500])
    print("--- MD 앞 300자 ---"); print(md[:300])


if __name__ == "__main__":
    main()
