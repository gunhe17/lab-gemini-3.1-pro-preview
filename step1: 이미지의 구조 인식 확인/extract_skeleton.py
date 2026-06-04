#!/usr/bin/env python3.12
"""골격 추출 — 열린(open) 재귀 JSON 트리.

정답(groundtruth) 없이, 모델이 표의 중첩 구조를 스스로 JSON 트리로 그리게 한다.
좌표·픽셀 금지(가설1), 위상(컨테이너 트리)만 요구. 셀 전체 전사 금지.

사용:
  python3.12 extract_skeleton.py            # inputs/ 전체 1회
  python3.12 extract_skeleton.py p-007      # 1장
  python3.12 extract_skeleton.py p-007 -k 3 # 일관성용 K회 반복
출력: outputs/p-NNN.skeleton.json  (k>1이면 outputs/p-NNN.k<i>.skeleton.json)
"""
import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
INPUTS = HERE / "inputs"
OUT = HERE / "outputs"
MODEL = "google/gemini-3.1-pro-preview"

SYSTEM = """너는 문서 이미지 속 표의 '구조 골격'을 분석한다.
좌표·픽셀·바운딩박스를 절대 보고하지 마라. 구조는 관계로만 서술한다.
JSON만 출력한다(설명·머리말·코드펜스 금지)."""

TASK = """이 이미지의 표 구조를 '골격'으로만 분석해 **열린 JSON 트리**로 출력하라.

원칙:
- 셀 내용을 전부 전사하지 마라. 구조 파악에 필요한 라벨 텍스트만 앵커로 참조하라.
- 좌표·픽셀·박스 금지. 위치는 읽을 수 있는 라벨 기준으로만.
- 중첩이 있으면 깊이 제한 없이 재귀적으로 펼쳐라.

각 노드는 자유롭게 표현하되, 최소한 다음을 담아라:
- 표 노드: 열 수, 행 수(또는 행 묶음), 그리고 셀들
- 각 셀: 그 안에 든 것의 종류를 구분 — 중첩표(table) / 텍스트덩어리(text, 불릿·번호 등) /
  빈 입력칸(empty) / 단순 라벨(label) — 와, 그 셀을 가리키는 앵커 라벨
- 병합이 있으면 어느 방향으로 몇 칸을 덮는지 관계로 표기

표가 여러 개면 최상위에 배열로 담아라. JSON만 출력하라."""


def load_env() -> None:
    env = HERE.parents[2] / ".env"
    if env.exists() and not os.environ.get("OPENROUTER_API_KEY"):
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def img_part(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


def call(path: Path) -> dict:
    key = os.environ["OPENROUTER_API_KEY"]
    payload = {
        "model": MODEL, "temperature": 1.0, "max_tokens": 16000,
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
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:500]}")


def parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", t, re.S)
        return json.loads(m.group(0)) if m else None


def run_one(page: str, tag: str = "") -> None:
    path = INPUTS / f"{page}.png"
    res = call(path)
    choice = res["choices"][0]
    text = choice["message"].get("content") or ""
    parsed = parse_json(text)
    OUT.mkdir(exist_ok=True)
    name = f"{page}{tag}.skeleton.json"
    (OUT / name).write_text(json.dumps(
        {"page": page, "usage": res.get("usage", {}),
         "parsed": parsed, "raw": text}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = "✓" if parsed is not None else "⚠ JSON 파싱 실패"
    print(f"{ok} {name}  usage={res.get('usage',{}).get('total_tokens','?')}tok "
          f"${res.get('usage',{}).get('cost','?')}")


def main() -> None:
    load_env()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    k = 1
    if "-k" in sys.argv:
        k = int(sys.argv[sys.argv.index("-k") + 1])
    pages = [args[0]] if args else [p.stem for p in sorted(INPUTS.glob("*.png"))]
    for page in pages:
        if k == 1:
            run_one(page)
        else:
            for i in range(1, k + 1):
                run_one(page, tag=f".k{i}")


if __name__ == "__main__":
    main()
