#!/usr/bin/env python3.12
"""U1 — 구조 골격 추출: 표 이미지 → 빈 셀 골격 HTML.

마스터플랜 U1. 내용 없이 격자·병합·중첩만 복원시키고(정규화 방지 프롬프트),
skeletonize로 정답·예측을 같은 형식으로 깎아 TEDS-Struct로 채점한다.
thinking_level은 OpenRouter reasoning.effort(low|medium|high)로 조절.

사용:
  python3.12 extract_u1.py s0-grid -t low      # 1장, 최소 사고
  python3.12 extract_u1.py -t low              # 전체 7장
출력: u1/<id>.<level>.html (모델 골격) + u1/<id>.<level>.json (raw+usage+TEDS)
"""
import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

from skeletonize import skeletonize
from teds import teds_struct_html

HERE = Path(__file__).parent
PNG = HERE / "png"
GT = HERE / "gt"
U1 = HERE / "u1"
MODEL = "google/gemini-3.1-pro-preview"

SYSTEM = """너는 표 이미지의 '구조 골격'을 그대로 복원하는 정밀 도구다.
셀 내용(텍스트)은 모두 빈칸으로 두고, <table>의 골격만 HTML로 출력한다.
설명·머리말·코드펜스 없이 <table>...</table> 만 출력한다."""

TASK = """이 이미지의 표 구조를 빈 셀 HTML 골격으로 복원하라.

규칙:
- 셀 안의 텍스트는 절대 옮기지 마라. 모든 셀은 빈 <td></td> 로 둔다.
- 보이는 병합을 rowspan/colspan 속성으로 그대로 표현하라. 격자를 가지런하게 다듬지 마라.
- 표 안에 표가 있으면 <td> 안에 중첩 <table>로 표현하라. 깊이 제한 없이 재귀.
- 보이는 것에만 근거하라. 일반적인 표 형태를 가정해 칸을 채우거나 정리하지 마라.
- <th>/<td> 구분은 신경 쓰지 말고 전부 <td>로 써도 된다.

<table>...</table> 만 출력하라."""


def load_key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    # 키는 repo_root/.env/.env 에 있음 (내용은 출력하지 않는다)
    envf = HERE.parents[1] / ".env" / ".env"
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("OPENROUTER_API_KEY 못 찾음 (.env/.env 확인)")


def img_part(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


def call(path: Path, level: str, key: str) -> dict:
    payload = {
        "model": MODEL, "temperature": 1.0, "max_tokens": 16000,
        "reasoning": {"effort": level},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [img_part(path), {"type": "text", "text": TASK}]},
        ],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:600]}")


def clean_html(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:html)?\s*|\s*```$", "", t, flags=re.S)
    m = re.search(r"<table.*</table>", t, re.S | re.I)
    return m.group(0) if m else t


def run_one(page: str, level: str, key: str) -> None:
    res = call(PNG / f"{page}.png", level, key)
    choice = res["choices"][0]
    raw = choice["message"].get("content") or ""
    pred_html = clean_html(raw)
    pred_skel = skeletonize(pred_html)
    gt_skel = (GT / f"{page}.skeleton.html").read_text(encoding="utf-8")
    score = teds_struct_html(pred_skel, gt_skel)
    U1.mkdir(exist_ok=True)
    (U1 / f"{page}.{level}.html").write_text(pred_skel + "\n", encoding="utf-8")
    usage = res.get("usage", {})
    (U1 / f"{page}.{level}.json").write_text(json.dumps(
        {"page": page, "level": level, "teds_struct": score,
         "usage": usage, "pred_skeleton": pred_skel, "raw": raw},
        ensure_ascii=False, indent=2), encoding="utf-8")
    rt = usage.get("completion_tokens_details", {}).get("reasoning_tokens", "?")
    print(f"{page:16} t={level:6} TEDS={score:.3f}  "
          f"reasoning={rt}tok total={usage.get('total_tokens','?')} ${usage.get('cost','?')}")


def main() -> None:
    key = load_key()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    level = "low"
    if "-t" in sys.argv:
        level = sys.argv[sys.argv.index("-t") + 1]
    pages = [args[0]] if args else [p.stem for p in sorted(PNG.glob("*.png"))]
    for page in pages:
        run_one(page, level, key)


if __name__ == "__main__":
    main()
