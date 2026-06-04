#!/usr/bin/env python3.12
"""U1 결과 비교 리포트 → compare-v<N>.html (입력 구성 버전별).

상단: 이 버전에서 **LLM에 들어간 입력 구성**(① system / ② few-shot / ③ task / 모델·파라미터)을
보기 좋게 정리. 하단: 샘플마다 [입력 PNG]·[정답 골격]·[예측 골격(thinking별)] + TEDS 배지.
골격 HTML은 빈 셀이라 테두리를 입혀 격자를 보이게 하고 중첩표는 색으로 강조한다.

사용:
  python3.12 build_compare.py          # 최신 버전(u1/v* 중 최대 N)
  python3.12 build_compare.py -v 1     # 특정 버전
출력: compare-v<N>.html  (입력 구성·실행 로그는 runlog-v<N>.md 와 짝)
"""
import base64
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
GT = HERE / "gt"
U1 = HERE / "u1"
PNG = HERE / "png"

LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}

CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:24px;background:#f5f5f7;color:#111;}
h1{font-size:20px;margin:0 0 4px;} .sub{color:#666;font-size:13px;margin:0 0 20px;}
/* 입력 구성 패널 */
.config{background:#0f1115;color:#e6e8ec;border-radius:10px;padding:18px 20px;margin:0 0 22px;}
.config h2{font-size:16px;margin:0 0 10px;color:#fff;}
.cfg-meta{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px;}
.pill{font-size:12px;background:#1d2230;border:1px solid #2c313c;border-radius:20px;padding:3px 11px;color:#9fd0ff;}
.config details{border:1px solid #2c313c;border-radius:8px;margin:0 0 8px;background:#15171d;}
.config summary{cursor:pointer;padding:8px 12px;font-weight:700;font-size:13px;color:#cdd3dd;}
.config pre.code{margin:0;padding:12px 14px;border-top:1px solid #2c313c;white-space:pre-wrap;
  font:12.5px/1.6 ui-monospace,Menlo,monospace;color:#c3e88d;overflow:auto;}
.config .muted{color:#8b93a1;padding:0 14px 12px;margin:0;}
.config .measure{margin:10px 0 0;padding:8px 12px;background:#15351c;border:1px solid #2c4a32;border-radius:8px;color:#c3e88d;font-size:12.5px;}
.config .fs{border-top:1px solid #2c313c;padding:10px 14px;}
.config .fs-cap{font-size:12px;color:#9fd0ff;margin-bottom:6px;}
.config .fs-row{display:flex;gap:12px;align-items:flex-start;}
.config .fs-row img{max-width:220px;border:1px solid #2c313c;background:#fff;border-radius:6px;}
/* 샘플 비교 */
.sample{background:#fff;border:1px solid #ddd;border-radius:10px;padding:16px 18px;margin:0 0 22px;}
.sample h2{font-size:16px;margin:0 0 12px;}
.cards{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;}
.card{border:1px solid #e0e0e0;border-radius:8px;padding:10px;background:#fafafa;}
.card .cap{font-size:12px;font-weight:700;margin-bottom:8px;display:flex;gap:8px;align-items:center;}
.card img{max-width:360px;height:auto;border:1px solid #ccc;background:#fff;}
.badge{font-size:11px;font-weight:700;border-radius:10px;padding:2px 8px;color:#fff;}
.b-gt{background:#3a7;} .b-ok{background:#2a8f2a;} .b-mid{background:#d98a00;} .b-bad{background:#c0392b;}
.b-info{background:#666;}
.skel table{border-collapse:collapse;background:#fff;}
.skel td{border:1.5px solid #444;min-width:20px;height:20px;padding:7px;}
.skel table table td{border-color:#c0392b;background:#fff5f4;}      /* 1단계 중첩 */
.skel table table table td{border-color:#8e44ad;background:#f8f2fb;} /* 2단계 중첩 */
.legend{font-size:12px;color:#555;margin:0 0 18px;}
.legend b{color:#c0392b;} .legend i{color:#8e44ad;font-style:normal;}
/* 비용·토큰 요약 */
.cost{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px 18px;margin:0 0 22px;}
.cost h2{font-size:15px;margin:0 0 10px;}
table.sum{border-collapse:collapse;width:100%;font-size:13px;}
table.sum th,table.sum td{border:1px solid #e3e3e3;padding:6px 10px;text-align:right;}
table.sum th{background:#f0f1f4;font-weight:700;}
table.sum td.l,table.sum th.l{text-align:left;}
table.sum tr.tot td{background:#0f1115;color:#fff;font-weight:700;border-color:#0f1115;}
table.sum .t-ok{color:#2a8f2a;font-weight:700;} table.sum .t-mid{color:#d98a00;font-weight:700;}
table.sum .t-bad{color:#c0392b;font-weight:700;}
"""


def esc(x) -> str:
    return html.escape(str(x))


def img_data_uri(p: Path) -> str:
    """PNG를 base64 data URI로 내장 — 리포트를 어느 폴더로 옮겨도 안 깨지게."""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def badge(teds: float) -> str:
    cls = "b-ok" if teds >= 0.999 else "b-mid" if teds >= 0.7 else "b-bad"
    return f'<span class="badge {cls}">TEDS {teds:.3f}</span>'


def card(cap_html: str, body_html: str) -> str:
    return f'<div class="card"><div class="cap">{cap_html}</div>{body_html}</div>'


def skel_block(html_text: str) -> str:
    return f'<div class="skel">{html_text}</div>'


def _ver_key(v: str) -> tuple:
    return tuple(int(p) for p in v.split("."))


def latest_version() -> str:
    vs = []
    for d in U1.glob("v*"):
        if d.is_dir() and (m := re.fullmatch(r"v(\d+(?:\.\d+)*)", d.name)):
            vs.append(m.group(1))
    return max(vs, key=_ver_key) if vs else "1"


def config_panel(cfg: dict) -> str:
    params = cfg.get("params", {})
    fs = cfg.get("fewshot", [])
    if fs:
        fs_html = "".join(
            f'<div class="fs"><div class="fs-cap">예시 {i + 1}</div>'
            f'<div class="fs-row"><img src="png/{esc(ex.get("image", ""))}" alt="few-shot {i + 1}"/>'
            f'<pre class="code">{esc(ex.get("output", ""))}</pre></div></div>'
            for i, ex in enumerate(fs))
    else:
        fs_html = '<p class="muted">(없음 — zero-shot)</p>'
    pills = [f'<span class="pill">model: {esc(cfg.get("model", "?"))}</span>']
    if cfg.get("backend"):
        pills.append(f'<span class="pill">backend: {esc(cfg["backend"])}</span>')
    for k, v in params.items():
        pills.append(f'<span class="pill">{esc(k)}: {esc(v)}</span>')
    axis = cfg.get("sweep_axis")
    pills.append(f'<span class="pill">sweep: {esc(axis)} (샘플별)</span>' if axis
                 else '<span class="pill">thinking: low·medium·high (샘플별)</span>')
    meta = "".join(pills)
    meas = (f'<p class="measure">측정: {esc(cfg["measurement"])}</p>'
            if cfg.get("measurement") else '')
    return f'''<section class="config">
  <h2>LLM 입력 구성 · v{esc(cfg.get("version", "?"))}</h2>
  <div class="cfg-meta">{meta}</div>
  {meas}
  <details open><summary>① system</summary><pre class="code">{esc(cfg.get("system", ""))}</pre></details>
  <details><summary>② few-shot ({len(fs)} shot)</summary>{fs_html}</details>
  <details open><summary>③ task (입력 지시 — 이미지와 함께 매 호출 전송)</summary><pre class="code">{esc(cfg.get("task", ""))}</pre></details>
</section>'''


def discover(vd: Path) -> dict:
    """{page: {level: {...}}}. 단일실행(구 형식)·반복측정(신 형식) 모두 지원."""
    pages: dict = {}
    for jf in sorted(vd.glob("*.json")):
        m = re.fullmatch(r"(.+)\.(low|medium|high)\.json", jf.name)
        if not m:
            continue
        page, level = m.group(1), m.group(2)
        meta = json.loads(jf.read_text(encoding="utf-8"))
        u = meta.get("usage_mean") or meta.get("usage") or {}
        reasoning = u.get("reasoning_tokens")
        if reasoning is None:
            reasoning = u.get("completion_tokens_details", {}).get("reasoning_tokens")
        n = meta.get("n", 1)
        teds = meta.get("teds_mean", meta.get("teds_struct", float("nan")))
        agreement = meta.get("agreement", 1.0)
        hf = vd / f"{page}.{level}.html"
        pages.setdefault(page, {})[level] = {
            "skel": hf.read_text(encoding="utf-8") if hf.exists() else "",
            "teds": teds,
            "std": meta.get("teds_std", 0.0),
            "n": n,
            "modal_count": round(agreement * n),
            "distinct": meta.get("distinct_structures", 1),
            "tmin": meta.get("teds_min"), "tmax": meta.get("teds_max"),
            "tokens": u.get("total_tokens"),
            "reasoning": reasoning,
            "cost": u.get("cost"),
        }
    return pages


def _num(x, default=0):
    return x if isinstance(x, (int, float)) else default


def cost_panel(pages: dict, cfg: dict) -> str:
    """샘플·조건별 TEDS·토큰·비용 + 총합. 조건 축은 config.sweep_axis(기본 thinking)."""
    axis = cfg.get("sweep_axis", "thinking")
    def tcls(t):
        return "t-ok" if t >= 0.999 else "t-mid" if t >= 0.7 else "t-bad"

    def money(c):
        return "—" if c is None else f"${c:.4f}"

    body, tot_cost, tot_tok, tot_rt, any_cost, any_rep = [], 0.0, 0, 0, False, False
    for page in sorted(pages):
        for level in sorted(pages[page], key=lambda l: LEVEL_ORDER.get(l, 9)):
            e = pages[page][level]
            tot_tok += _num(e["tokens"]); tot_rt += _num(e["reasoning"])
            if e["cost"] is not None:
                tot_cost += e["cost"]; any_cost = True
            teds, n = e["teds"], e["n"]
            teds_cell = f'{teds:.3f} ± {e["std"]:.3f}' if n > 1 else f'{teds:.3f}'
            if n > 1:
                any_rep = True
                agree = f'{e["modal_count"]}/{n} ({e["distinct"]}종)'
            else:
                agree = '1/1'
            body.append(
                f'<tr><td class="l">{esc(page)}</td><td class="l">{esc(level)}</td>'
                f'<td class="{tcls(teds)}">{teds_cell}</td>'
                f'<td>{esc(agree)}</td>'
                f'<td>{esc(e["tokens"] if e["tokens"] is not None else "?")}</td>'
                f'<td>{money(e["cost"])}</td></tr>')
    cnt = sum(len(v) for v in pages.values())
    total = (f'<tr class="tot"><td class="l" colspan="2">합계 · {cnt}조건</td>'
             f'<td></td><td></td><td>{tot_tok:,}</td>'
             f'<td>{money(tot_cost) if any_cost else "— (네이티브 $미보고)"}</td></tr>')
    note = ('<p class="legend">TEDS = n회 반복의 <b>평균 ± 표준편차</b>, 구조열 = 최빈 구조 동의수/n (서로 다른 구조 종수). '
            '단일 실행(n=1)은 ±0·1/1로 표시 — 고엔트로피 샘플에선 신뢰 낮음.</p>' if any_rep else '')
    return f'''<section class="cost">
  <h2>비용·토큰·안정성 요약</h2>
  {note}
  <table class="sum">
    <thead><tr><th class="l">샘플</th><th class="l">{esc(axis)}</th><th>TEDS (평균±σ)</th>
      <th>구조 동의 (modal/n)</th><th>토큰(평균)</th><th>비용(USD)</th></tr></thead>
    <tbody>{"".join(body)}{total}</tbody>
  </table>
</section>'''


def main() -> None:
    version = latest_version()
    if "-v" in sys.argv:
        version = sys.argv[sys.argv.index("-v") + 1]
    vd = U1 / f"v{version}"
    cfg_f = vd / "_config.json"
    cfg = json.loads(cfg_f.read_text(encoding="utf-8")) if cfg_f.exists() else {"version": version}

    pages = discover(vd)
    rows = []
    for page in sorted(pages):
        levels = pages[page]
        cards = []
        png = PNG / f"{page}.png"
        if png.exists():
            cards.append(card('<span class="badge b-info">입력 PNG</span>',
                              f'<img src="{img_data_uri(png)}"/>'))
        gt = GT / f"{page}.skeleton.html"
        if gt.exists():
            cards.append(card('<span class="badge b-gt">정답 골격</span>',
                              skel_block(gt.read_text(encoding="utf-8"))))
        for level in sorted(levels, key=lambda l: LEVEL_ORDER.get(l, 9)):
            e = levels[level]
            n = e["n"]
            extra = (f' <span class="badge b-info">±{e["std"]:.3f} · {e["modal_count"]}/{n} modal</span>'
                     if n > 1 else '')
            lab = f'예측(modal) · {level}' if n > 1 else f'예측 · {level}'
            cap = f'<span class="badge b-info">{lab}</span>{badge(e["teds"])}{extra}'
            cards.append(card(cap, skel_block(e["skel"])))
        rows.append(f'<div class="sample"><h2>{esc(page)}</h2><div class="cards">{"".join(cards)}</div></div>')

    n = sum(len(v) for v in pages.values())
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>U1 골격 비교 · v{version}</title><style>{CSS}</style></head><body>
<h1>U1 구조 골격 — 정답 vs 모델 출력 · v{version}</h1>
<p class="sub">{len(pages)}샘플 · 예측 {n}건 · <a href="log.html">실행 로그</a> · <a href="../../index.html">← 전체 인덱스</a></p>
{config_panel(cfg)}
{cost_panel(pages, cfg)}
<p class="legend">테두리 색: 검정=외곽표, <b>빨강=1단계 중첩표</b>, <i>보라=2단계 중첩표</i>.
점수 배지 초록(완벽)/주황(부분)/빨강(붕괴).</p>
{"".join(rows)}
</body></html>"""
    out = vd / "report.html"
    out.write_text(doc, encoding="utf-8")
    print(f"✓ u1/v{version}/report.html  ({len(pages)}샘플, 예측 {n}건)")


if __name__ == "__main__":
    main()
