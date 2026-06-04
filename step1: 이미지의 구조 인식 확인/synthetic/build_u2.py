#!/usr/bin/env python3.12
"""U2 해리 검사 결과 → reports/u2-dissociation.html (자체완결).

u2/*.json(질문별 분포) + u2/_verdict.md(자동 판정)를 읽어 보기 좋은 리포트로.
지각(perception) vs 생산(production) 판정을 한 화면에. PNG는 base64 내장.
사용: python3 build_u2.py
"""
import base64
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
U2 = HERE / "u2"
PNG = HERE / "png"
ORDER = ["control_outer", "target_cells", "target_lines"]
LABEL = {"control_outer": "대조 · 바깥표 머리글 칸 수",
         "target_cells": "타깃 · 중첩표 윗줄 칸 수",
         "target_lines": "타깃 · 윗줄 내부 세로선 수"}


def esc(x) -> str:
    return html.escape(str(x))


def verdict_text() -> str:
    f = U2 / "_verdict.md"
    if not f.exists():
        return "(판정 없음 — extract_u2.py 먼저 실행)"
    md = f.read_text(encoding="utf-8")
    # '## 자동 판정' 이후 본문만 추출
    if "## 자동 판정" in md:
        md = md.split("## 자동 판정", 1)[1]
    return md.strip()


def md_inline(s: str) -> str:
    s = esc(s)
    import re
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def main() -> None:
    recs = {}
    for qid in ORDER:
        f = U2 / f"{qid}.json"
        if f.exists():
            recs[qid] = json.loads(f.read_text(encoding="utf-8"))
    if not recs:
        raise SystemExit("u2/*.json 없음 — extract_u2.py 먼저 실행")

    meta = next(iter(recs.values()))
    rows = []
    for qid in ORDER:
        r = recs.get(qid)
        if not r:
            continue
        ok = (r["modal"] == r["gt"])
        cls = "ok" if ok else "bad"
        rows.append(
            f'<tr><td class="l">{esc(LABEL[qid])}</td>'
            f'<td>{esc(r["kind"])}</td><td>{r["gt"]}</td>'
            f'<td class="mono">{esc(r["answers"])}</td>'
            f'<td class="{cls}">{esc(r["modal"])} ({r["modal_count"]}/{r["n"]})</td>'
            f'<td class="{cls}">{r["correct_rate"]:.2f}</td></tr>')

    raws = []
    for qid in ORDER:
        r = recs.get(qid)
        if not r:
            continue
        items = "".join(f"<li><b>{esc(a)}</b> · <span class=mut>{esc((rw or '').strip()[:80])}</span></li>"
                        for a, rw in zip(r["answers"], r.get("raws", [])))
        raws.append(f'<details><summary>{esc(LABEL[qid])} — 질문·원답 {r["n"]}회</summary>'
                    f'<p class="q">{esc(r["question"])}</p><ol>{items}</ol></details>')

    png = PNG / "s6-p011clone.png"
    img = ('<img src="data:image/png;base64,' + base64.b64encode(png.read_bytes()).decode() + '"/>'
           if png.exists() else "")

    v = md_inline(verdict_text())
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>U2 해리 검사 — 지각 vs 생산</title><style>
body{{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:24px;background:#f5f5f7;color:#111;max-width:1100px;}}
h1{{font-size:20px;margin:0 0 4px;}} .sub{{color:#666;font-size:13px;margin:0 0 18px;}}
.sub a{{color:#2a6;}}
.grid{{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;}}
.col-img{{flex:0 0 300px;}} .col-img img{{width:100%;border:1px solid #ccc;border-radius:8px;background:#fff;}}
.col-main{{flex:1;min-width:420px;}}
.verdict{{background:#0f1115;color:#e6e8ec;border-radius:10px;padding:16px 18px;margin:0 0 18px;line-height:1.6;}}
.verdict b{{color:#7cff9b;}} .verdict code{{background:#1d2230;color:#9fd0ff;padding:1px 5px;border-radius:4px;}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:0 0 16px;background:#fff;}}
th,td{{border:1px solid #e0e0e0;padding:7px 10px;text-align:center;}}
th{{background:#f0f1f4;}} td.l{{text-align:left;}} td.mono,.mono{{font-family:ui-monospace,Menlo,monospace;}}
td.ok{{color:#2a8f2a;font-weight:700;}} td.bad{{color:#c0392b;font-weight:700;}}
details{{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:8px 12px;margin:0 0 8px;}}
summary{{cursor:pointer;font-weight:700;font-size:13px;}}
.q{{color:#444;font-size:12.5px;background:#f7f7f9;padding:6px 8px;border-radius:6px;}}
ol{{font-size:12.5px;}} .mut{{color:#888;}}
.note{{font-size:12px;color:#666;border-left:3px solid #ccc;padding-left:10px;margin-top:14px;}}
</style></head><body>
<h1>U2 해리 검사 — 지각(perception) vs 생산(production)</h1>
<p class="sub">{esc(meta.get('id') and 's6-p011clone')} · model gemini-3.1-pro-preview ·
media_resolution={esc(meta.get('media_resolution'))} · thinking={esc(meta.get('thinking_level'))} ·
temperature={esc(meta.get('temperature'))} · n={esc(meta.get('n'))} ·
<a href="verdict.html">verdict</a> · <a href="../index.html">← 전체 인덱스</a></p>
<div class="verdict">{v}</div>
<div class="grid">
  <div class="col-img"><div class="sub">입력(s6) — 질문은 '기존' 칸 안 '㉔ 위기관리 지원' 목록이 든 작은 표의 맨 윗줄을 가리킴</div>{img}</div>
  <div class="col-main">
    <table><thead><tr><th class="l">질문</th><th>종류</th><th>정답</th><th>답 분포(n회)</th><th>최빈(동의)</th><th>정답률</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
    {"".join(raws)}
    <p class="note">HTML(U1)을 우회하고 '개수'만 물어 직렬화를 빼고 <b>지각 단독</b>을 측정.
    대조가 맞아야 타깃 오답이 의미를 가짐. 칸 수 ↔ 내부 세로선 수로 삼각측량(칸=선+1).</p>
  </div>
</div>
</body></html>"""
    (U2 / "report.html").write_text(doc, encoding="utf-8")
    print(f"✓ u2/report.html  ({len(recs)}질문)")


if __name__ == "__main__":
    main()
