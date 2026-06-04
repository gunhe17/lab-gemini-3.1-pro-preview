#!/usr/bin/env python3.12
"""U1 결과 시각 비교 리포트 빌더 → compare.html.

샘플마다 [입력 PNG] · [정답 골격] · [예측 골격(thinking별)]을 나란히 렌더.
골격 HTML은 빈 셀이라, 테두리를 입혀 격자가 보이게 하고 중첩표는 빨강으로 강조.
TEDS 점수를 배지로 띄워 한눈에 비교.

사용: python3.12 build_compare.py   → compare.html
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
GT = HERE / "gt"
U1 = HERE / "u1"
PNG = HERE / "png"
OUT = HERE / "compare.html"

LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}

CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:24px;background:#f5f5f7;color:#111;}
h1{font-size:20px;margin:0 0 4px;} .sub{color:#666;font-size:13px;margin:0 0 20px;}
.sample{background:#fff;border:1px solid #ddd;border-radius:10px;padding:16px 18px;margin:0 0 22px;}
.sample h2{font-size:16px;margin:0 0 12px;}
.cards{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;}
.card{border:1px solid #e0e0e0;border-radius:8px;padding:10px;background:#fafafa;}
.card .cap{font-size:12px;font-weight:700;margin-bottom:8px;display:flex;gap:8px;align-items:center;}
.card img{max-width:360px;height:auto;border:1px solid #ccc;background:#fff;}
.badge{font-size:11px;font-weight:700;border-radius:10px;padding:2px 8px;color:#fff;}
.b-gt{background:#3a7;} .b-ok{background:#2a8f2a;} .b-mid{background:#d98a00;} .b-bad{background:#c0392b;}
.b-info{background:#666;}
/* 골격 렌더 */
.skel table{border-collapse:collapse;background:#fff;}
.skel td{border:1.5px solid #444;min-width:20px;height:20px;padding:7px;}
.skel table table td{border-color:#c0392b;background:#fff5f4;}      /* 1단계 중첩 */
.skel table table table td{border-color:#8e44ad;background:#f8f2fb;} /* 2단계 중첩 */
.legend{font-size:12px;color:#555;margin:0 0 18px;}
.legend b{color:#c0392b;} .legend i{color:#8e44ad;font-style:normal;}
"""


def badge(teds: float) -> str:
    if teds >= 0.999:
        cls = "b-ok"
    elif teds >= 0.7:
        cls = "b-mid"
    else:
        cls = "b-bad"
    return f'<span class="badge {cls}">TEDS {teds:.3f}</span>'


def card(cap_html: str, body_html: str) -> str:
    return f'<div class="card"><div class="cap">{cap_html}</div>{body_html}</div>'


def skel_block(html: str) -> str:
    return f'<div class="skel">{html}</div>'


def discover():
    """{page: {"levels": {level: (skel_html, teds)}}} (사다리 순 정렬)."""
    pages = {}
    for jf in sorted(U1.glob("*.*.json")):
        m = re.match(r"(.+)\.(low|medium|high)\.json$", jf.name)
        if not m:
            continue
        page, level = m.group(1), m.group(2)
        meta = json.loads(jf.read_text(encoding="utf-8"))
        skel = (U1 / f"{page}.{level}.html").read_text(encoding="utf-8")
        pages.setdefault(page, {})[level] = (skel, meta.get("teds_struct", float("nan")))
    return pages


def main() -> None:
    pages = discover()
    rows = []
    for page in sorted(pages):
        levels = pages[page]
        cards = []
        # 입력 PNG
        png = PNG / f"{page}.png"
        if png.exists():
            cards.append(card('<span class="badge b-info">입력 PNG</span>',
                              f'<img src="png/{page}.png"/>'))
        # 정답 골격
        gt = GT / f"{page}.skeleton.html"
        if gt.exists():
            cards.append(card('<span class="badge b-gt">정답 골격</span>',
                              skel_block(gt.read_text(encoding="utf-8"))))
        # 예측 골격 (thinking 순)
        for level in sorted(levels, key=lambda l: LEVEL_ORDER.get(l, 9)):
            skel, teds = levels[level]
            cap = f'<span class="badge b-info">예측 · {level}</span>{badge(teds)}'
            cards.append(card(cap, skel_block(skel)))
        rows.append(f'<div class="sample"><h2>{page}</h2><div class="cards">{"".join(cards)}</div></div>')

    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>U1 골격 비교</title><style>{CSS}</style></head><body>
<h1>U1 구조 골격 — 정답 vs 모델 출력</h1>
<p class="sub">빈 셀 골격을 렌더. TEDS-Struct 점수 배지로 비교.</p>
<p class="legend">테두리 색: 검정=외곽표, <b>빨강=1단계 중첩표</b>, <i>보라=2단계 중첩표</i>.
초록 배지=정답, 점수 배지 초록(완벽)/주황(부분)/빨강(붕괴).</p>
{"".join(rows)}
</body></html>"""
    OUT.write_text(html, encoding="utf-8")
    n = sum(len(v) for v in pages.values())
    print(f"✓ {OUT.name}  ({len(pages)}샘플, 예측 {n}건)")


if __name__ == "__main__":
    main()
