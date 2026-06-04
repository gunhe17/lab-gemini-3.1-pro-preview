#!/usr/bin/env python3
"""u3 콘텐츠 변환 시각 리포트 → u3/report.html (자체완결).

모델별로 [모델 HTML 렌더] + [모델 MD 렌더]를, 입력 PNG·소스 GT와 비교.
콘텐츠(텍스트)까지 보이게 실제 표로 렌더. MD는 markdown 라이브러리로 렌더(표 확장).
사용: ../../.venv/bin/python build_u3_report.py   (markdown 라이브러리 필요)
"""
import base64
import html as _html
import json
import re
from pathlib import Path

import markdown

HERE = Path(__file__).parent
U3 = HERE / "u3"
PAGE = "s6-p011clone"
PNGF = HERE / "png" / f"{PAGE}.png"
GT_SRC = (HERE / "html" / f"{PAGE}.html").read_text(encoding="utf-8")

CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:24px;background:#f5f5f7;color:#111;}
h1{font-size:20px;margin:0 0 4px;} .sub{color:#666;font-size:13px;margin:0 0 18px;}
h2{font-size:16px;margin:22px 0 8px;border-bottom:2px solid #d8d9de;padding-bottom:5px;}
.cols{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;}
.col{flex:1;min-width:340px;border:1px solid #e0e0e0;border-radius:8px;background:#fff;padding:10px 12px;}
.col .cap{font-size:12px;font-weight:700;margin-bottom:8px;display:flex;gap:8px;align-items:center;}
.col img{max-width:100%;border:1px solid #ccc;}
.badge{font-size:11px;font-weight:700;border-radius:10px;padding:2px 8px;color:#fff;}
.b-ok{background:#2a8f2a;} .b-mid{background:#d98a00;} .b-bad{background:#c0392b;} .b-gt{background:#3a7;} .b-info{background:#666;}
/* 콘텐츠 표 렌더 */
.render{font-size:11.5px;overflow:auto;max-height:70vh;}
.render table{border-collapse:collapse;width:100%;}
.render td,.render th{border:1px solid #555;padding:4px 6px;vertical-align:top;line-height:1.4;}
.render table table td{border-color:#c0392b;background:#fff6f5;}   /* 1단계 중첩 */
.render ul{margin:2px 0;padding-left:16px;} .render li{margin:1px 0;}
.render p{margin:4px 0;color:#444;}
.note{font-size:12px;color:#555;border-left:3px solid #ccc;padding-left:10px;margin:0 0 14px;}
details{margin-top:8px;font-size:12px;} summary{cursor:pointer;color:#1769d6;}
pre{white-space:pre-wrap;background:#0f1115;color:#c3e88d;padding:8px;border-radius:6px;font-size:11px;overflow:auto;}
"""


def esc(x):
    return _html.escape(str(x))


def table_of(h):
    m = re.search(r"<table.*</table>", h or "", re.S | re.I)
    return m.group(0) if m else ""


def badge(v):
    cls = "b-ok" if v is not None and v >= 0.95 else "b-mid" if v is not None and v >= 0.7 else "b-bad"
    return f'<span class="badge {cls}">{v:.3f}</span>' if v is not None else '<span class="badge b-bad">—</span>'


def main():
    png = "data:image/png;base64," + base64.b64encode(PNGF.read_bytes()).decode()
    recs = []
    for f in sorted(U3.glob("*.json")):
        recs.append(json.loads(f.read_text(encoding="utf-8")))

    # 상단: 입력 + 소스 GT
    top = (
        f'<div class="cols">'
        f'<div class="col"><div class="cap"><span class="badge b-info">입력 PNG (s6)</span></div>'
        f'<img src="{png}"/></div>'
        f'<div class="col"><div class="cap"><span class="badge b-gt">소스 GT (정답 내용)</span></div>'
        f'<div class="render">{table_of(GT_SRC)}</div></div>'
        f'</div>'
    )

    blocks = [top]
    for r in recs:
        name = esc(r.get("model"))
        cs, st = r.get("content_sim"), r.get("struct_teds")
        md_html = markdown.markdown(r.get("markdown") or "", extensions=["tables", "fenced_code"])
        raw_md = esc(r.get("markdown") or "")
        blocks.append(
            f'<h2>{name} <span class="sub">[{esc(r.get("prompt",""))}]</span></h2>'
            f'<p class="note">콘텐츠 유사도 {badge(cs)} (텍스트 전사 정확도, vs 소스) · '
            f'구조 TEDS {badge(st)} (vs 중첩 GT 골격)</p>'
            f'<div class="cols">'
            f'<div class="col"><div class="cap"><span class="badge b-info">모델 HTML (렌더)</span></div>'
            f'<div class="render">{table_of(r.get("html"))}</div></div>'
            f'<div class="col"><div class="cap"><span class="badge b-info">모델 Markdown (렌더)</span></div>'
            f'<div class="render">{md_html}</div>'
            f'<details><summary>raw markdown</summary><pre>{raw_md}</pre></details></div>'
            f'</div>'
        )

    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<title>u3 콘텐츠 변환 — HTML/MD</title><style>{CSS}</style></head><body>
<h1>u3 — 완전 콘텐츠 변환 (이미지 → HTML + Markdown)</h1>
<p class="sub">입력 s6(실문서 중첩 난표) · 모델이 텍스트까지 변환한 결과를 실제로 렌더. 콘텐츠 유사도=텍스트 전사 정확도, 구조 TEDS=골격 정확도.</p>
{"".join(blocks)}
</body></html>"""
    out = U3 / "report.html"
    out.write_text(doc, encoding="utf-8")
    print(f"✓ u3/report.html  (모델 {len(recs)}개)")


if __name__ == "__main__":
    main()
