#!/usr/bin/env python3
"""Anthropic Claude(OpenRouter)로 s6 표 골격 추출 — Gemini 수준→상위 점진 사다리.

동일 조건: 프롬프트 v1.1 · temperature=1.0 · n=5 · 확장사고 끔(Gemini thinking=low 대응).
OpenRouter chat/completions 직접 호출(무릴레이). 채점=skeletonize+TEDS-Struct vs 중첩 GT.
결과는 flash/ 와 같은 스키마로 <tag>/u1_s6-p011clone.json 에 저장 + print.

사다리(낮은→높은): sonnet-4.6(91.2, ≈Gemini 테스트수준) → opus-4.6 → opus-4.8
사용: ../../../.venv/bin/python run_claude.py
"""
import base64
import json
import re
import statistics
import sys
import time
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize
from teds import teds_struct_html
from extract_u1 import PROMPTS

SYSTEM = PROMPTS["1.1"]["system"]
TASK = PROMPTS["1.1"]["task"]

# Claude 전용 재프롬프트(docs/claude-prompting.md 반영): <example> few-shot · 맥락 · 긍정형 규칙 · 자가검증 · XML.
# Claude가 s6에서 범한 오류(표 밖 문단을 표행으로 흡수 / 빈칸 병합)를 예시·규칙·체크로 직격.
CLAUDE_SYSTEM = """<role>
너는 문서 이미지 속 표의 '구조 골격'을 복원하는 정밀 변환 도구다. 표의 기하(행·열 격자·병합·중첩)만 다룬다.
</role>
<definitions>
- 골격: 행·열 격자 + 병합(colspan/rowspan) + 중첩만 남기고 텍스트·스타일은 제외한 구조.
- 셀: 격자의 한 칸. 비어 있어도 하나의 셀이다.
- 중첩: 한 <td> 안에 또 다른 <table>이 들어간 것.
</definitions>
<rules>
- 보이는 격자선과 정렬에 근거해 격자를 복원한다.
- 비어 있는 칸도 각각 별도의 <td></td> 로 센다.
- 인접한 칸은 그 사이를 가르는 선이 실제로 안 보일 때만 colspan/rowspan으로 합친다.
- 셀 안의 표는 중첩 <table>로 유지하고 깊이 제한 없이 재귀한다.
- 표의 바깥이나 아래에 있는 문단 글(절차 설명·비고 등)은 표의 행이 아니다. 표에 포함하지 않는다.
- <th>/<td> 구분 없이 모두 <td>로 쓴다.
</rules>
<output_format>
<table>...</table> 하나만 출력한다. 설명·머리말·코드펜스 없이.
</output_format>"""

CLAUDE_TASK = """<context>
이 골격은 다운스트림 파이프라인이 표를 재구성하는 데 쓰인다. 빈 칸·병합·중첩이 정확해야 하고, 표 밖 문단이 표에 섞이면 안 된다.
</context>

<example>
설명: 2열 표. 머리글 [항목|값]. 본문 행의 왼쪽 칸은 비어 있고(앞 페이지 병합 연속), 오른쪽 칸 안에는 3열짜리 작은 표가 들어 있다. 그 표 아래에는 "비고: …" 문단이 있다.
정답 골격:
<table>
  <tr><td></td><td></td></tr>
  <tr>
    <td></td>
    <td>
      <table>
        <tr><td></td><td></td><td></td></tr>
      </table>
    </td>
  </tr>
</table>
(빈 왼쪽 칸도 별도 <td> · 셀 안 표는 중첩 <table> · "비고:" 문단은 표 밖이라 행으로 넣지 않음)
</example>

<task>
첨부 이미지의 표 구조를 빈 셀 HTML 골격으로 복원하라.
</task>

<self_check>
출력 직전 점검: (1) 표 바깥/아래의 문단 글을 표 행으로 넣지 않았는가? (2) 비어 보이는 칸도 각각 별도 <td>로 셌는가(임의 병합 금지)? (3) 셀 안의 표를 중첩 <table>로 유지했는가?
</self_check>

위 점검을 거쳐 <table>...</table> 만 출력하라."""
PNG = SYN / "png"
GT = (SYN / "gt" / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
PAGE = "s6-p011clone"
N, TEMP = 5, 1.0
REASONING = None   # --think 시 {"max_tokens": 6000}
SUFFIX = ""

LADDER = [
    ("anthropic/claude-sonnet-4.6", "sonnet-4.6"),   # 리더보드 TEDS-S 91.2 ≈ Gemini 수준
    ("anthropic/claude-opus-4.6", "opus-4.6"),
    ("anthropic/claude-opus-4.8", "opus-4.8"),
]
_HARD = ("401", "402", "403", "400", "No endpoints", "insufficient")
_TRANSIENT = ("429", "500", "502", "503", "timeout", "Overloaded")


def load_key():
    import os
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for line in (SYN.parents[1] / ".env" / ".env").read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("OPENROUTER_API_KEY 못 찾음")


KEY = load_key()


def img_part(p):
    b = base64.b64encode(p.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}}


def call(model):
    mt = 16000
    if REASONING:
        mt = max(mt, REASONING["max_tokens"] + 8000)  # 사고예산 + 출력 여유
    payload = {
        "model": model, "temperature": TEMP, "max_tokens": mt,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [img_part(PNG / f"{PAGE}.png"), {"type": "text", "text": TASK}]},
        ],
    }
    if REASONING:
        payload["reasoning"] = REASONING
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = f"{e.code} {e.read().decode()[:200]}"
            if any(h in msg for h in _HARD):
                sys.exit(f"하드 오류: {msg}")
            if attempt < 3 and any(t in msg for t in _TRANSIENT):
                time.sleep(10 * (attempt + 1)); continue
            raise


def clean(t):
    t = (t or "").strip()
    t = re.sub(r"^```(?:html)?\s*|\s*```$", "", t, flags=re.S)
    m = re.search(r"<table.*</table>", t, re.S | re.I)
    return m.group(0) if m else t


def run_model(model, tag):
    runs = []
    for i in range(N):
        res = call(model)
        raw = res["choices"][0]["message"].get("content") or ""
        skel = skeletonize(clean(raw))
        runs.append({"teds": teds_struct_html(skel, GT), "skel": skel,
                     "cost": res.get("usage", {}).get("cost"),
                     "total_tokens": res.get("usage", {}).get("total_tokens")})
    scores = [r["teds"] for r in runs]
    skels = Counter(r["skel"] for r in runs)
    ms, mc = skels.most_common(1)[0]
    costs = [r["cost"] for r in runs if isinstance(r["cost"], (int, float))]
    rec = {
        "model": model, "page": PAGE, "n": N, "temperature": TEMP,
        "teds_mean": statistics.mean(scores), "teds_std": statistics.pstdev(scores) if N > 1 else 0.0,
        "teds_min": min(scores), "teds_max": max(scores), "scores": scores,
        "modal_teds": next(r["teds"] for r in runs if r["skel"] == ms),
        "agreement": mc / N, "distinct": len(skels), "modal_skeleton": ms,
        "reasoning": REASONING,
        "cost_total_usd": round(sum(costs), 5) if costs else None,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    out = HERE / f"{tag}{SUFFIX}" / f"u1_{PAGE}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{tag:12} TEDS={rec['teds_mean']:.3f}±{rec['teds_std']:.3f} "
          f"(n={N}, 동의 {mc}/{N}, 구조 {len(skels)}종, range {min(scores):.3f}~{max(scores):.3f}) "
          f"${rec['cost_total_usd']}", flush=True)


def main():
    global REASONING, SUFFIX, SYSTEM, TASK
    args = sys.argv[1:]
    ladder = LADDER
    if "--think" in args:
        budget = int(args[args.index("--budget") + 1]) if "--budget" in args else 6000
        REASONING = {"max_tokens": budget}
        SUFFIX = "-think" if budget == 6000 else f"-think{budget // 1000}k"
        ladder = [("anthropic/claude-sonnet-4.6", "sonnet-4.6"),
                  ("anthropic/claude-opus-4.8", "opus-4.8")]
    if "--cprompt" in args:
        SYSTEM, TASK = CLAUDE_SYSTEM, CLAUDE_TASK
        SUFFIX += "-cprompt"
    if "--model" in args:
        only = args[args.index("--model") + 1]
        ladder = [(m, t) for m, t in ladder if t == only] or [(f"anthropic/claude-{only}", only)]
    mode = f"확장사고 ON(budget {REASONING['max_tokens']})" if REASONING else "확장사고 끔"
    print(f"sample={PAGE} · 프롬프트 v1.1 · temp={TEMP} · n={N} · {mode} · 채점=TEDS vs 중첩GT")
    print(f"(기준선: Gemini 3-flash 0.875 / 3.1-pro 0.850 / PaddleOCR 0.531)\n")
    for model, tag in ladder:
        run_model(model, tag)


if __name__ == "__main__":
    main()
