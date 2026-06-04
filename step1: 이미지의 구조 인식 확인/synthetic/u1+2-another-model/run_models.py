#!/usr/bin/env python3.12
"""u1(마지막=v2.1) · u2(해리 검사)를 다른 Gemini 모델로 재시험 + 비교 렌더.

배경: OmniDocBench TEDS-S에서 gemini-3.1-pro(85.4) < gemini-3-pro(91.7) < gemini-3-flash(92.6).
같은 벤더 안에서 모델만 내려도 표 구조가 오르는지 직접 확인.

- 부모(synthetic)의 skeletonize·teds·v1.1 프롬프트·U2 질문을 재사용. PNG·GT도 부모 것.
- u1: s6 media_resolution 스윕(low/medium/high, n=5) + s4 대조(high, n=3). thinking=low, temp=1.0.
- u2: 해리 3질문(control/target_cells/target_lines, n=5), mr=high.
- 현재 3.1-pro 수치는 부모 u1/v2.1·u2 결과를 읽어 함께 비교.
- 단위별 json 저장 → 중단/재개 안전(이미 있으면 skip).

사용:  ../../../.venv/bin/python run_models.py            # 전체
       ../../../.venv/bin/python run_models.py --render   # 호출 없이 렌더만
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

HERE = Path(__file__).parent          # u1+2-another-model/
SYN = HERE.parent                     # synthetic/
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize          # noqa: E402
from teds import teds_struct_html            # noqa: E402
from extract_u1 import PROMPTS               # noqa: E402
from extract_u2 import QUESTIONS as U2Q, SYSTEM as U2_SYS, parse_int  # noqa: E402

PNG = SYN / "png"
GT = SYN / "gt"

# gemini-3-pro-preview 는 404(폐기)라 테스트 불가 → 목록에 있던 최신 gemini-3.5-flash 로 대체.
MODELS = [("gemini-3-flash-preview", "flash"), ("gemini-3.5-flash", "flash35")]
CURRENT = ("gemini-3.1-pro-preview", "current")  # 부모 결과에서 읽음
RETIRED_NOTE = "gemini-3-pro-preview는 404 NOT_FOUND(폐기)로 테스트 불가 — 최신 gemini-3.5-flash로 대체."
MR_LEVELS = ["low", "medium", "high"]
N, N_CTRL, TEMP, THINKING = 5, 3, 1.0, "low"

U1_SYS = PROMPTS["1.1"]["system"]
U1_TASK = PROMPTS["1.1"]["task"]

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
    for line in (SYN.parents[1] / ".env" / ".env").read_text().splitlines():
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


def ask(model, png_bytes, system, task, mr, max_out):
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=TEMP, max_output_tokens=max_out,
        media_resolution=_MRES[mr], thinking_config=types.ThinkingConfig(thinking_level=_TL[THINKING]))
    contents = [types.Content(role="user", parts=[
        types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
        types.Part.from_text(text=task)])]
    for attempt in range(4):
        try:
            r = client().models.generate_content(model=model, contents=contents, config=cfg)
            return r.text or ""
        except Exception as e:
            msg = str(e).replace("\n", " ")
            if any(h in msg for h in _HARD):
                sys.exit(f"하드 오류 — 계정/모델 접근 확인. 중단.\n{msg[:200]}")
            if attempt < 3 and any(t in msg for t in _TRANSIENT):
                time.sleep(15 * (attempt + 1))
            else:
                raise


def clean_html(t):
    t = (t or "").strip()
    t = re.sub(r"^```(?:html)?\s*|\s*```$", "", t, flags=re.S)
    m = re.search(r"<table.*</table>", t, re.S | re.I)
    return m.group(0) if m else t


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── u1: 구조 TEDS (s6 mr 스윕, s4 대조) ───────────────────────────────────────

def run_u1_unit(model, tag, page, mr, n):
    out = HERE / tag / f"u1_{page}.{mr}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    gt_skel = (GT / f"{page}.skeleton.html").read_text(encoding="utf-8")
    png_bytes = (PNG / f"{page}.png").read_bytes()
    runs = []
    for _ in range(n):
        raw = ask(model, png_bytes, U1_SYS, U1_TASK, mr, 16000)
        skel = skeletonize(clean_html(raw))
        runs.append({"teds": teds_struct_html(skel, gt_skel), "skel": skel})
    scores = [r["teds"] for r in runs]
    skels = Counter(r["skel"] for r in runs)
    modal_skel, modal_n = skels.most_common(1)[0]
    rec = {"model": model, "page": page, "mr": mr, "n": n,
           "teds_mean": statistics.mean(scores),
           "teds_std": statistics.pstdev(scores) if n > 1 else 0.0,
           "teds_min": min(scores), "teds_max": max(scores), "scores": scores,
           "modal_teds": next(r["teds"] for r in runs if r["skel"] == modal_skel),
           "agreement": modal_n / n, "distinct": len(skels),
           "modal_skeleton": modal_skel, "timestamp": now()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [u1] {tag:7} {page:14} mr={mr:6} TEDS={rec['teds_mean']:.3f}±{rec['teds_std']:.3f} "
          f"(agree {modal_n}/{n})", flush=True)
    return rec


# ── u2: 해리 검사(개수 질문) ─────────────────────────────────────────────────

def run_u2_unit(model, tag, qd, n):
    out = HERE / tag / f"u2_{qd['id']}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    png_bytes = (PNG / "s6-p011clone.png").read_bytes()
    raws, answers = [], []
    for _ in range(n):
        raw = ask(model, png_bytes, U2_SYS, qd["q"], "high", 4000)
        raws.append(raw.strip())
        answers.append(parse_int(raw))
    valid = [a for a in answers if a is not None]
    cnt = Counter(valid)
    modal, modal_n = (cnt.most_common(1)[0] if cnt else (None, 0))
    rec = {"model": model, "id": qd["id"], "kind": qd["kind"], "gt": qd["gt"], "n": n,
           "answers": answers, "modal": modal, "modal_count": modal_n,
           "agreement": (modal_n / n if modal is not None else 0.0), "distinct": len(cnt),
           "correct_rate": (sum(1 for a in valid if a == qd["gt"]) / n), "raws": raws, "timestamp": now()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [u2] {tag:7} {qd['id']:14} gt={qd['gt']} modal={modal}({modal_n}/{n}) "
          f"answers={answers}", flush=True)
    return rec


# ── 현재(3.1-pro) 결과는 부모에서 읽음 ────────────────────────────────────────

def current_u1(page, mr):
    f = SYN / "u1" / "v2.1" / f"{page}.{mr}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    return {"teds_mean": d.get("teds_mean"), "teds_std": d.get("teds_std", 0.0),
            "agreement": d.get("agreement"), "n": d.get("n")}


def current_u2(qid):
    f = SYN / "u2" / f"{qid}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    return {"modal": d.get("modal"), "agreement": d.get("agreement"),
            "gt": d.get("gt"), "correct_rate": d.get("correct_rate")}


# ── 렌더 ──────────────────────────────────────────────────────────────────────

CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:28px;background:#f5f5f7;color:#111;max-width:1000px;}
h1{font-size:21px;margin:0 0 4px;} .sub{color:#666;font-size:13px;margin:0 0 20px;}
h2{font-size:16px;margin:24px 0 6px;border-bottom:2px solid #d8d9de;padding-bottom:5px;}
table{border-collapse:collapse;width:100%;font-size:13px;margin:0 0 8px;background:#fff;}
th,td{border:1px solid #e0e0e0;padding:7px 10px;text-align:center;} th{background:#f0f1f4;}
td.l,th.l{text-align:left;} .cur{background:#fbf3f3;} .win{color:#2a8f2a;font-weight:700;} .lose{color:#c0392b;}
.mut{color:#888;font-size:11px;} .note{font-size:12px;color:#555;border-left:3px solid #ccc;padding-left:10px;margin:6px 0 16px;}
.tag{font-size:11px;color:#888;font-weight:400;}
.box{background:#0f1115;color:#e6e8ec;border-radius:10px;padding:14px 20px;margin:0 0 16px;}
.box b{color:#7cff9b;} .box ul{margin:8px 0 0;padding-left:18px;} .box li{margin:6px 0;line-height:1.55;font-size:13px;}
.box b{color:#fff;} .box li b{color:#7cff9b;}
table.lb{max-width:420px;} table.lb td{text-align:right;} table.lb td.l{text-align:left;}
"""


def u1_cell(d, base, is_current):
    if not d or d.get("teds_mean") is None:
        return '<td class="mut">—</td>'
    txt = f'{d["teds_mean"]:.3f} ± {d.get("teds_std", 0):.3f}'
    cls = ""
    if not is_current and base and base.get("teds_mean") is not None:
        diff = d["teds_mean"] - base["teds_mean"]
        if diff > 0.005:
            cls, txt = " win", txt + f' <span class="mut">▲{diff:+.3f}</span>'
        elif diff < -0.005:
            cls, txt = " lose", txt + f' <span class="mut">▼{diff:+.3f}</span>'
    return f'<td class="{cls.strip()}">{txt}</td>'


def u2_cell(d):
    if not d or d.get("modal") is None:
        return '<td class="mut">—</td>'
    cls = "win" if d["modal"] == d["gt"] else "lose"
    ag = d.get("agreement")
    agr = f' <span class="mut">({ag:.0%})</span>' if ag is not None else ""
    return f'<td class="{cls}">{d["modal"]}{agr}</td>'


def render():
    models = [CURRENT] + MODELS  # 현재, flash, flash35
    label = {"current": "gemini-3.1-pro (현재)", "flash": "gemini-3-flash", "flash35": "gemini-3.5-flash"}
    u1, u2 = {}, {}
    for mid, tag in models:
        u1[tag] = {mr: (current_u1("s6-p011clone", mr) if tag == "current"
                        else _load(tag, f"u1_s6-p011clone.{mr}.json")) for mr in MR_LEVELS}
        u1[tag]["s4"] = (current_u1("s4-nested-asym", "high") if tag == "current"
                         else _load(tag, "u1_s4-nested-asym.high.json"))
        u2[tag] = {q["id"]: (current_u2(q["id"]) if tag == "current"
                             else _load(tag, f"u2_{q['id']}.json")) for q in U2Q}
    base = u1["current"]

    u1_rows = []
    for mid, tag in models:
        cur = tag == "current"
        cells = "".join(u1_cell(u1[tag][mr], base[mr], cur) for mr in MR_LEVELS) + u1_cell(u1[tag]["s4"], base["s4"], cur)
        u1_rows.append(f'<tr{" class=cur" if cur else ""}><td class="l">{label[tag]}</td>{cells}</tr>')
    u1_tbl = (f'<table><thead><tr><th class="l">모델</th><th>s6 · mr=low</th><th>s6 · mr=medium</th>'
              f'<th>s6 · mr=high</th><th>s4 · high(대조)</th></tr></thead><tbody>{"".join(u1_rows)}</tbody></table>')

    u2_rows = []
    for mid, tag in models:
        cells = "".join(u2_cell(u2[tag][q["id"]]) for q in U2Q)
        u2_rows.append(f'<tr{" class=cur" if tag == "current" else ""}><td class="l">{label[tag]}</td>{cells}</tr>')
    heads = "".join(f'<th>{q["id"]}<br><span class="tag">정답 {q["gt"]}</span></th>' for q in U2Q)
    u2_tbl = f'<table><thead><tr><th class="l">모델</th>{heads}</tr></thead><tbody>{"".join(u2_rows)}</tbody></table>'

    # 자동 요약
    bullets = []
    fh, ch = u1["flash"]["high"], base["high"]
    if fh and ch and fh.get("teds_mean") is not None:
        d = fh["teds_mean"] - ch["teds_mean"]
        bullets.append(f"구조(s6 high): gemini-3-flash <b>{fh['teds_mean']:.3f}±{fh.get('teds_std',0):.3f}</b> "
                       f"vs 현재 {ch['teds_mean']:.3f}±{ch.get('teds_std',0):.3f} → <b>{d:+.3f}</b>, "
                       f"분산 {ch.get('teds_std',0):.3f}→{fh.get('teds_std',0):.3f}. "
                       f"flash가 더 높고 더 안정 — 단 modal 천장 0.875는 동일.")
    ftc, ctc = u2["flash"].get("target_cells"), u2["current"].get("target_cells")
    if ftc and ctc and ftc.get("modal") is not None:
        flick = "한 번 '3' 회수" if 3 in (_load("flash", "u2_target_cells.json") or {}).get("answers", []) else ""
        bullets.append(f"지각(target_cells, 정답 3): 현재 modal {ctc['modal']}({ctc.get('agreement',0):.0%}) · "
                       f"flash modal {ftc['modal']}({ftc.get('agreement',0):.0%}) {('— '+flick) if flick else ''}. "
                       f"→ 두 모델 다 주로 '2'(빈칸 병합). <b>지각 한계는 대체로 공유</b> — 교체만으론 천장 못 뚫음.")
    f35tc, f35h = u2["flash35"].get("target_cells"), u1["flash35"]["high"]
    if f35tc and f35tc.get("modal") is not None and f35h and f35h.get("teds_mean") is not None:
        ag5 = round((f35h.get("agreement") or 0) * (f35h.get("n") or 5))
        bullets.append(f"gemini-3.5-flash 역설: 지각 target_cells modal <b>{f35tc['modal']}</b>({f35tc.get('agreement',0):.0%}) — "
                       f"<b>처음으로 '3' 다수 회수</b>(지각은 모델 의존·개선 가능). 그런데 구조 s6 high는 "
                       f"{f35h['teds_mean']:.3f}±{f35h.get('teds_std',0):.3f}로 <b>가장 불안정</b>(동의 {ag5}/5)이고 "
                       f"target_lines는 여전히 1 → 지각이 일관되지 않아 더 나은 출력으로 이어지지 않음.")
    bullets.append("결론: <b>실용 최선은 gemini-3-flash</b> — 0.875 modal을 5/5(σ=0)로 신뢰, 더 싸고, 리더보드 1위. "
                   "3.5-flash는 더 새것이나 표 구조는 더 불안정(리더보드 미수록과 일치). "
                   "단 <b>어느 모델도 0.875 천장(빈칸 병합)은 못 뚫음</b> → 그 잔여는 <b>VLM + 결정론적 선검출 하이브리드</b>로만 해결.")
    summary = "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"

    # 전용 파서(별도 채점 — 표현 정규화 주의)
    ded_html = ""
    ded_f = HERE / "dedicated_results.json"
    if ded_f.exists():
        import json as _json
        ded = _json.load(open(ded_f, encoding="utf-8"))
        rows = []
        for name, d in ded.items():
            raw = d.get("raw_teds_nested_gt")
            rawc = "—" if raw is None else f"{raw:.3f}"
            rows.append(f'<tr><td class="l">{name}</td><td>{rawc}</td>'
                        f'<td class="l">{d.get("encoding","—")}</td>'
                        f'<td class="l">{d.get("perception_empty_cells","—")}</td></tr>')
        ded_html = (
            '<h2>전용 파서 (s6) <span class="tag">⚠ 나이브 TEDS는 중첩 GT 기준 — 평탄 인코딩을 과소평가</span></h2>'
            '<p class="note">PaddleOCR-VL-1.6은 s6를 <b>평탄 9열</b>로 파싱(같은 격자의 다른 인코딩). '
            '나이브 TEDS 0.531은 Gemini의 0.875와 직접 비교 불가 — 컨벤션 차이일 뿐. '
            '<b>핵심: 본문 행을 [빈칸|내용|빈칸]으로 분리해, U2에서 Gemini가 병합(2칸)한 빈 칸을 정확히 포착.</b> '
            '공정 비교엔 표현 정규화(flatten-then-TEDS) 필요.</p>'
            '<table><thead><tr><th class="l">모델</th><th>나이브 TEDS<br><span class="tag">중첩 GT 기준</span></th>'
            '<th class="l">인코딩</th><th class="l">빈칸 지각</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')

    lb = ("<table class='lb'><thead><tr><th class='l'>OmniDocBench TEDS-S</th><th>점수</th></tr></thead><tbody>"
          "<tr><td class='l'>Gemini-3-Flash</td><td>92.6</td></tr>"
          "<tr><td class='l'>Gemini-3-Pro <span class='mut'>(폐기·테스트불가)</span></td><td>91.7</td></tr>"
          "<tr class='cur'><td class='l'>Gemini-3.1-Pro (현재)</td><td>85.4</td></tr>"
          "<tr><td class='l'>Gemini-3.5-Flash</td><td class='mut'>리더보드 미수록</td></tr></tbody></table>")

    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>모델 비교 — u1·u2 재시험</title><style>{CSS}</style></head><body>
<h1>다른 Gemini 모델로 u1·u2 재시험</h1>
<p class="sub">동일 조건(프롬프트 v1.1 · thinking=low · temperature=1.0 · n=5) · 입력 s6/s4 ·
<a href="../index.html">← 전체 인덱스</a></p>
<div class="box"><b>요약</b>{summary}</div>
<p class="note">⚠ {RETIRED_NOTE}</p>

<h2>u1 — 구조 골격 TEDS <span class="tag">평균±σ (높을수록 좋음 · ▲/▼=현재 대비)</span></h2>
{u1_tbl}

<h2>u2 — 해리 검사(지각) <span class="tag">개수 질문 최빈답 (정답 일치=초록 · 괄호=동의율)</span></h2>
<p class="note">핵심 <b>target_cells</b>(중첩표 윗줄 칸 수, 정답 3): 현재 3.1-pro는 5/5로 '2'(빈칸 병합)=지각 실패.</p>
{u2_tbl}

{ded_html}

<h2>참고 — OmniDocBench TEDS-S 리더보드</h2>
{lb}
</body></html>"""
    (HERE / "index.html").write_text(doc, encoding="utf-8")
    print(f"✓ {HERE.name}/index.html")


def _load(tag, fname):
    f = HERE / tag / fname
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def main():
    if "--render" in sys.argv:
        render()
        return
    for mid, tag in MODELS:
        print(f"=== {tag} ({mid}) ===", flush=True)
        for mr in MR_LEVELS:
            run_u1_unit(mid, tag, "s6-p011clone", mr, N)
        run_u1_unit(mid, tag, "s4-nested-asym", "high", N_CTRL)
        for q in U2Q:
            run_u2_unit(mid, tag, q, N)
    render()


if __name__ == "__main__":
    main()
