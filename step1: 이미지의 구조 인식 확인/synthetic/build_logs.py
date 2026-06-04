#!/usr/bin/env python3.12
"""마크다운 런로그·판정 → 같은 폴더의 HTML (브라우저 렌더용).

u1/v*/runlog.md → u1/v*/log.html,  u2/_verdict.md → u2/verdict.html.
각 버전 폴더 안에서 데이터·리포트·로그가 함께 있게. (마크다운 lib 필요 — venv)
사용: ./.venv/bin/python build_logs.py
"""
from pathlib import Path

import markdown

HERE = Path(__file__).parent
U1 = HERE / "u1"
U2 = HERE / "u2"

CSS = """
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;margin:0;padding:28px;
  background:#f5f5f7;color:#1a1d24;max-width:920px;line-height:1.65;}
a.back{font-size:13px;color:#1769d6;text-decoration:none;}
article{background:#fff;border:1px solid #e2e2e6;border-radius:10px;padding:20px 26px;margin-top:12px;}
h1{font-size:20px;} h2{font-size:16px;border-bottom:1px solid #e4e4e8;padding-bottom:5px;margin-top:26px;}
h3{font-size:14px;margin-top:20px;color:#0a3;}
code{background:#eef0f3;padding:1px 5px;border-radius:4px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px;}
pre{background:#0f1115;color:#c3e88d;padding:12px 14px;border-radius:8px;overflow:auto;font-size:12px;line-height:1.5;}
pre code{background:none;color:inherit;padding:0;}
details{background:#fafbfc;border:1px solid #e4e4e8;border-radius:7px;padding:6px 12px;margin:6px 0;}
summary{cursor:pointer;font-weight:700;font-size:13px;}
table{border-collapse:collapse;} th,td{border:1px solid #ddd;padding:5px 9px;font-size:13px;}
th{background:#f0f1f4;} strong{color:#111;} ul{margin:6px 0;}
"""


def render(md_text: str, title: str, back: str) -> str:
    body = markdown.markdown(
        md_text, extensions=["fenced_code", "tables", "sane_lists", "md_in_html"])
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"/>'
            f'<title>{title}</title><style>{CSS}</style></head><body>'
            f'<a class="back" href="{back}">← 전체 인덱스</a>'
            f'<article>{body}</article></body></html>')


def main() -> None:
    n = 0
    for d in sorted(U1.glob("v*")):
        f = d / "runlog.md"
        if f.exists():
            (d / "log.html").write_text(
                render(f.read_text(encoding="utf-8"), f"실행 로그 {d.name}", "../../index.html"),
                encoding="utf-8")
            print(f"✓ u1/{d.name}/log.html"); n += 1
    vf = U2 / "_verdict.md"
    if vf.exists():
        (U2 / "verdict.html").write_text(
            render(vf.read_text(encoding="utf-8"), "U2 판정", "../index.html"), encoding="utf-8")
        print("✓ u2/verdict.html"); n += 1
    print(f"({n}개 렌더)")


if __name__ == "__main__":
    main()
