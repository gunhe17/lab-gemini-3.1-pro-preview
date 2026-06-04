#!/usr/bin/env python3
"""U2 해리 검사(지각) — Claude(OpenRouter)판. Gemini U2와 동일 질문/채점.

Gemini(3.1-pro)는 target_cells=2(5/5, 빈칸 병합)로 지각 실패였다. opus-4.8 +확장사고가
같은 질문에 '3'을 맞히는지 = "Claude의 빈칸 지각이 더 정확"을 직접 검증.
질문은 extract_u2와 동일(import). 결과는 opus-4.8-think/u2_*.json (flash 구조와 동형).
사용: ../../../.venv/bin/python run_claude_u2.py
"""
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from extract_u2 import QUESTIONS, SYSTEM as U2_SYS, parse_int  # 동일 질문/파서
sys.path.insert(0, str(HERE))
from run_claude import KEY, img_part, PNG, PAGE, _HARD, _TRANSIENT

MODEL, TAG = "anthropic/claude-opus-4.8", "opus-4.8-think"
N, TEMP = 5, 1.0
REASONING = {"max_tokens": 6000}        # 확장사고 ON (구조 테스트와 동일)
PRODUCTION_SAW = 2                       # Gemini가 그 줄을 그린 칸 수(병합)


def ask(q):
    mt = (REASONING["max_tokens"] + 8000) if REASONING else 4000
    payload = {"model": MODEL, "temperature": TEMP, "max_tokens": mt,
               "messages": [{"role": "system", "content": U2_SYS},
                            {"role": "user", "content": [img_part(PNG / f"{PAGE}.png"),
                                                         {"type": "text", "text": q}]}]}
    if REASONING:
        payload["reasoning"] = REASONING
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            msg = f"{e.code} {e.read().decode()[:160]}"
            if any(h in msg for h in _HARD):
                sys.exit(f"하드 오류: {msg}")
            if attempt < 3 and any(t in msg for t in _TRANSIENT):
                time.sleep(10 * (attempt + 1)); continue
            raise


def run_q(qd):
    raws, ans = [], []
    for _ in range(N):
        raw = ask(qd["q"])
        raws.append(raw.strip())
        ans.append(parse_int(raw))
    valid = [a for a in ans if a is not None]
    cnt = Counter(valid)
    modal, mc = (cnt.most_common(1)[0] if cnt else (None, 0))
    rec = {"model": MODEL, "id": qd["id"], "kind": qd["kind"], "gt": qd["gt"], "n": N,
           "reasoning": REASONING, "answers": ans, "modal": modal, "modal_count": mc,
           "agreement": (mc / N if modal is not None else 0.0), "distinct": len(cnt),
           "correct_rate": sum(1 for a in valid if a == qd["gt"]) / N, "raws": raws,
           "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    out = HERE / TAG / f"u2_{qd['id']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{qd['id']:14} gt={qd['gt']} answers={ans} modal={modal}({mc}/{N}) "
          f"agree={rec['agreement']:.2f} correct={rec['correct_rate']:.2f}", flush=True)
    return rec


def main():
    print(f"U2 on {MODEL} · 확장사고 budget {REASONING['max_tokens']} · n={N}")
    print("(Gemini 3.1-pro U2: control 5/5=5 · target_cells 5/5=2(실패) · target_lines=1)\n")
    recs = {q["id"]: run_q(q) for q in QUESTIONS}
    tc, ctrl = recs["target_cells"], recs["control_outer"]
    print()
    if ctrl["modal"] != 5:
        print(f"측정 무효: 대조(바깥 머리글) modal={ctrl['modal']} (≠5)")
    elif tc["modal"] == 3:
        print(f"✅ Claude는 그 줄을 3칸으로 봄(modal=3, {tc['modal_count']}/{N}) — "
              f"Gemini가 병합(2)한 빈칸을 정확히 지각. 지각에서 Claude 우위.")
    elif tc["modal"] is not None and tc["modal"] <= 2:
        print(f"Claude도 2칸 이하로 봄(modal={tc['modal']}) — Gemini와 같은 빈칸 병합.")
    else:
        print(f"불안정(modal={tc['modal']}, {tc['distinct']}종) — 지각 고엔트로피.")


if __name__ == "__main__":
    main()
