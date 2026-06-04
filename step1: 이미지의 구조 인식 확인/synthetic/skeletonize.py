#!/usr/bin/env python3.12
"""HTML → 빈 셀 골격 HTML 정규화기.

정답(우리 HTML)이든 모델 출력이든 **같은 함수**에 통과시켜 동일 형식으로 만든다.
남기는 것: table / tr / td + colspan·rowspan + 중첩표.
버리는 것: 텍스트, 스타일, class, th/td 구분(전부 td로 통일), ul·div 등 비표 요소.
→ TEDS-Struct가 사과 대 사과로 격자 기하(병합·중첩)만 채점하게 한다.

사용:
  python3.12 skeletonize.py            # html/*.html → gt/<id>.skeleton.html
  python3.12 skeletonize.py s4-nested-asym
"""
import sys
from pathlib import Path

from extract_gt import TableTreeParser, Table  # 같은 디렉터리 파서 재사용

HERE = Path(__file__).parent
HTML = HERE / "html"
GT = HERE / "gt"


def emit(table: Table, indent: int) -> str:
    pad = "  " * indent
    out = [f"{pad}<table>"]
    for row in table.rows:
        out.append(f"{pad}  <tr>")
        for cell in row.cells:
            attr = ""
            if cell.colspan != 1:
                attr += f' colspan="{cell.colspan}"'
            if cell.rowspan != 1:
                attr += f' rowspan="{cell.rowspan}"'
            if cell.children:  # 중첩표 — td 안에 재귀
                out.append(f"{pad}    <td{attr}>")
                for child in cell.children:
                    out.append(emit(child, indent + 3))
                out.append(f"{pad}    </td>")
            else:
                out.append(f"{pad}    <td{attr}></td>")
        out.append(f"{pad}  </tr>")
    out.append(f"{pad}</table>")
    return "\n".join(out)


def skeletonize(html_text: str) -> str:
    """HTML 문자열 → 골격 HTML 문자열. 루트 표가 여럿이면 순서대로 나열."""
    p = TableTreeParser()
    p.feed(html_text)
    return "\n".join(emit(t, 0) for t in p.roots)


def main() -> None:
    GT.mkdir(exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = [HTML / f"{args[0]}.html"] if args else sorted(HTML.glob("*.html"))
    for f in files:
        skel = skeletonize(f.read_text(encoding="utf-8"))
        out = GT / f"{f.stem}.skeleton.html"
        out.write_text(skel + "\n", encoding="utf-8")
        cells = skel.count("<td")
        tables = skel.count("<table")
        print(f"✓ {out.name}  (table {tables}, td {cells})")


if __name__ == "__main__":
    main()
