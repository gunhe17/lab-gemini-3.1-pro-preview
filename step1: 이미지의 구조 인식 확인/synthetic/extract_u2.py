#!/usr/bin/env python3.12
"""U2 — 해리 검사(dissociation test): 지각(perception) vs 생산(production) 분리.

U1(HTML 골격 출력)은 '지각 + 직렬화'를 한 덩어리로 측정해 둘을 못 가른다.
U2는 HTML을 거치지 않고 **"그 칸이 몇 개냐"** 만 물어, 자기회귀 직렬화를 우회하고
**지각 단계만 단독으로** 본다. s6의 잔여 오차(빈 vlabel칸을 colspan=2로 병합)가
'못 본 것(지각)'인지 '봤는데 받아쓰다 망친 것(생산)'인지 판정.

설계(피드백 반영):
- 유도 금지: 예/아니오(sycophancy) 대신 **개방형 개수** 질문.
- 삼각측량: 같은 줄의 '칸 수'와 '내부 세로 구분선 수'를 둘 다 물어 교차검증(칸=선+1).
- 대조(control): 모델이 항상 맞히는 바깥표 머리글 칸 수(=5)도 물어 측정 타당성 확인.
- 지칭: 좌표 대신 **읽히는 텍스트 앵커**('기존' 칸 / '㉔ 위기관리 지원' 목록)로 영역 지정.
- 반복: media_resolution=high(HTML이 4/5로 수렴한 조건) · thinking=low · temp=1.0 · n=5.
  질문은 HTML 생성과 **별도 호출**(독립 측정).

판정 매트릭스(자동):
  대조 실패            → 측정 무효(모델이 쉬운 개수도 못 셈)
  target 칸=3 신뢰     → 생산 실패(지각 정상) · 모델 교체 불필요, 출력 전략으로 해결
  target 칸≤2 신뢰     → 지각 실패 확정 · 모델 교체 정당
  target 칸 들쭉날쭉   → 지각 고엔트로피(입력 정보 부족)

사용:  ./.venv/bin/python extract_u2.py [-n 5] [-mr high] [-temp 1.0]
출력:  u2/<qid>.json (질문별 분포) · u2/_verdict.md (자동 판정)
"""
import json
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).parent
PNG = HERE / "png"
U2 = HERE / "u2"
PAGE = "s6-p011clone"
MODEL = "gemini-3.1-pro-preview"

MR = "high"          # HTML이 4/5로 수렴한 조건과 맞춤
THINKING = "low"     # HTML 생산 조건과 동일 → 사과 대 사과
TEMP = 1.0
N = 5

# s6 high HTML 생산에서 모델이 그 줄을 실제로 그린 칸 수(= colspan2 → 2칸으로 병합).
PRODUCTION_SAW_CELLS = 2

SYSTEM = ("너는 이미지 속 표를 주의 깊게 관찰해, 묻는 '개수'만 정수 하나로 답한다. "
          "추측하지 말고 보이는 대로 센다. 설명·단위·문장 없이 숫자 하나만 출력한다.")

# gt: 정답 개수 / kind: control|target / line: 삼각측량 파트너
QUESTIONS = [
    {"id": "control_outer", "kind": "control", "gt": 5,
     "q": ("이 이미지에서 가장 바깥(가장 큰) 표를 보라. '구분', '사업명', '항목', '기존', '변경'이 "
           "적힌 맨 윗 행은 세로 칸(셀)이 몇 개로 나뉘어 있는가? 숫자만 답하라.")},
    {"id": "target_cells", "kind": "target", "gt": 3,
     "q": ("이 이미지의 '기존' 칸 안에는 작은 표가 하나 들어 있다. 그 작은 표에서 "
           "'㉔ 위기관리 지원' 글머리 목록이 들어 있는 맨 윗줄을 보라. "
           "그 줄은 세로 칸(셀)이 몇 개로 나뉘어 있는가? 숫자만 답하라.")},
    {"id": "target_lines", "kind": "target", "gt": 2,
     "q": ("이 이미지의 '기존' 칸 안 작은 표에서, '㉔ 위기관리 지원' 목록이 든 맨 윗줄을 보라. "
           "그 줄에서 칸과 칸을 좌우로 가르는 '안쪽' 세로 구분선은 몇 개 보이는가? "
           "(바깥 테두리 선은 제외) 숫자만 답하라.")},
]

_MRES = {"low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
         "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
         "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH}
_TL = {"low": types.ThinkingLevel.LOW, "medium": types.ThinkingLevel.MEDIUM, "high": types.ThinkingLevel.HIGH}
_TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")
_HARD = ("PERMISSION_DENIED", "403", "401", "400")


def load_key() -> str:
    import os
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    for line in (HERE.parents[1] / ".env" / ".env").read_text().splitlines():
        line = line.strip()
        if line.startswith("GEMINI_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("GEMINI_API_KEY 못 찾음")


_CLIENT = None


def client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = genai.Client(api_key=load_key())
    return _CLIENT


def ask(png_bytes: bytes, q: str) -> str:
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM, temperature=TEMP, max_output_tokens=4000,
        media_resolution=_MRES[MR],
        thinking_config=types.ThinkingConfig(thinking_level=_TL[THINKING]),
    )
    contents = [types.Content(role="user", parts=[
        types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
        types.Part.from_text(text=q),
    ])]
    for attempt in range(4):
        try:
            r = client().models.generate_content(model=MODEL, contents=contents, config=cfg)
            return r.text or ""
        except Exception as e:
            msg = str(e).replace("\n", " ")
            if any(h in msg for h in _HARD):
                sys.exit(f"하드 오류 — 계정/프로젝트 확인. 중단.\n{msg[:200]}")
            if attempt < 3 and any(t in msg for t in _TRANSIENT):
                time.sleep(15 * (attempt + 1))
            else:
                raise


def parse_int(text: str):
    for tok in re.findall(r"\d+", text or ""):
        v = int(tok)
        if 1 <= v <= 30:
            return v
    return None


def run_question(qd: dict, png_bytes: bytes) -> dict:
    raws, answers = [], []
    for _ in range(N):
        raw = ask(png_bytes, qd["q"])
        raws.append(raw.strip())
        answers.append(parse_int(raw))
    valid = [a for a in answers if a is not None]
    cnt = Counter(valid)
    modal, modal_n = (cnt.most_common(1)[0] if cnt else (None, 0))
    agreement = modal_n / N if modal is not None else 0.0
    rec = {
        "id": qd["id"], "kind": qd["kind"], "gt": qd["gt"], "question": qd["q"],
        "media_resolution": MR, "thinking_level": THINKING, "temperature": TEMP, "n": N,
        "answers": answers, "modal": modal, "modal_count": modal_n,
        "agreement": agreement, "distinct": len(cnt),
        "correct_rate": (sum(1 for a in valid if a == qd["gt"]) / N),
        "raws": raws,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    U2.mkdir(exist_ok=True)
    (U2 / f"{qd['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{qd['id']:14} gt={qd['gt']} answers={answers} modal={modal}({modal_n}/{N}) "
          f"agree={agreement:.2f} correct={rec['correct_rate']:.2f}", flush=True)
    return rec


def verdict(recs: dict) -> str:
    ctrl = recs["control_outer"]
    tc = recs["target_cells"]
    tl = recs.get("target_lines", {})
    control_ok = ctrl["modal"] == ctrl["gt"] and ctrl["agreement"] >= 0.6

    if not control_ok:
        v = ("**측정 무효 (INCONCLUSIVE)** — 대조 질문(바깥 머리글=5)조차 못 맞힘"
             f"(modal={ctrl['modal']}, agree={ctrl['agreement']:.2f}). 질문 형식/지칭부터 재점검.")
    elif tc["modal"] == 3 and tc["agreement"] >= 0.6:
        v = ("**생산 실패 · 지각 정상** — 모델은 그 줄을 3칸으로 정확히 본다"
             f"(modal=3, agree={tc['agreement']:.2f}). 그런데 HTML 생산에선 2칸(colspan=2)으로 병합. "
             "→ 정보는 모델 안에 있고 **자기회귀 직렬화에서만 잃는다.** "
             "모델 교체 불필요 — 출력 전략(중간표현·셀단위 분해·관계 재질의)으로 해결.")
    elif tc["modal"] is not None and tc["modal"] <= 2 and tc["agreement"] >= 0.6:
        v = ("**지각 실패 확정** — 모델이 그 줄을 실제로 2칸 이하로 본다"
             f"(modal={tc['modal']}, agree={tc['agreement']:.2f}), HTML과 일치. "
             "→ 픽셀에서 정보가 소실. **전용/상위 모델 교체가 정당해진다.**")
    else:
        v = ("**지각 고엔트로피** — 그 줄 칸 수가 호출마다 흔들림"
             f"(answers={tc['answers']}, agree={tc['agreement']:.2f}). "
             "→ 그 영역 정보가 입력에 충분치 않다 = 지각 한계. 해상도/표식 등 입력 보강 필요.")

    # 삼각측량 정합성
    tri = ""
    if tl and tl.get("modal") is not None and tc.get("modal") is not None:
        consistent = (tc["modal"] == tl["modal"] + 1)
        tri = (f"\n- 삼각측량: 칸 수 modal={tc['modal']} ↔ 내부 세로선 modal={tl['modal']} "
               f"→ {'정합(칸=선+1) ✓' if consistent else '불일치 ⚠ (질문 해석 갈림 가능)'}")
    return v + tri


def main():
    global MR, THINKING, TEMP, N
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-n": N = int(argv[i + 1]); i += 2; continue
        if a == "-mr": MR = argv[i + 1]; i += 2; continue
        if a == "-temp": TEMP = float(argv[i + 1]); i += 2; continue
        i += 1
    if MR not in _MRES:
        sys.exit(f"-mr 은 {list(_MRES)} 중 하나")
    png_bytes = (PNG / f"{PAGE}.png").read_bytes()
    recs = {q["id"]: run_question(q, png_bytes) for q in QUESTIONS}

    md = [
        f"# U2 해리 검사 — {PAGE} (지각 vs 생산)\n",
        f"model `{MODEL}` · media_resolution=`{MR}` · thinking=`{THINKING}` · temperature=`{TEMP}` · n={N}",
        "HTML(U1)을 우회하고 개수만 물어 **지각 단독** 측정. 비교 기준: s6 high HTML 생산에서 "
        f"그 줄을 **{PRODUCTION_SAW_CELLS}칸(colspan=2)으로 병합**해 그림.\n",
        "| 질문 | 종류 | 정답 | 답 분포 | 최빈(동의) | 정답률 |",
        "|------|------|:--:|---------|:--:|:--:|",
    ]
    for q in QUESTIONS:
        r = recs[q["id"]]
        md.append(f"| {q['id']} | {q['kind']} | {q['gt']} | `{r['answers']}` | "
                  f"{r['modal']} ({r['modal_count']}/{N}) | {r['correct_rate']:.2f} |")
    md += ["", "## 자동 판정\n", verdict(recs), "",
           "> 주의: target이 정답이어도 (a) '지각 정상+직렬화 실패' 와 "
           "(b) '질문이 그 영역에 주의를 집중시켜 연산을 더 쓴 것' 두 해석이 가능. "
           "다만 어느 쪽이든 '그 픽셀에서 정답 회수 가능' → 모델의 눈이 아니라 출력 방식을 바꾸는 쪽."]
    U2.mkdir(exist_ok=True)
    (U2 / "_verdict.md").write_text("\n".join(md), encoding="utf-8")
    print("\n" + verdict(recs))
    print(f"\n✓ u2/_verdict.md · u2/*.json ({len(QUESTIONS)}질문 × n={N})")


if __name__ == "__main__":
    main()
