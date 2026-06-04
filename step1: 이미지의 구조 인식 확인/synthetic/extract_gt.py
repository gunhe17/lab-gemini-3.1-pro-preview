#!/usr/bin/env python3.12
"""HTML(우리가 작성한 정답) → 골격 JSON 추출기.

우리가 직접 쓴 HTML이므로 이 출력이 곧 정답(GT). 모델 출력과 같은 스키마로 내보내
같은 채점기(TEDS·diff)를 재사용한다. rowspan/colspan을 그리드 점유로 정규화해
'진짜 열 수'를 계산하고, 모든 본문 행이 그 열 수로 해소되는지(consistency)도 기록한다.

사용:
  python3.12 extract_gt.py            # html/*.html 전체 → gt/<id>.gt.json
  python3.12 extract_gt.py s4-nested-asym
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).parent
HTML = HERE / "html"
GT = HERE / "gt"

CELL_TAGS = {"td", "th"}


class Cell:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.text_parts = []
        self.children = []  # 중첩 Table

    @property
    def colspan(self):
        return int(self.attrs.get("colspan", 1))

    @property
    def rowspan(self):
        return int(self.attrs.get("rowspan", 1))

    @property
    def text(self):
        return re.sub(r"\s+", " ", "".join(self.text_parts)).strip()


class Row:
    def __init__(self):
        self.cells = []


class Table:
    def __init__(self):
        self.rows = []


class TableTreeParser(HTMLParser):
    """table/tr/td/th만 추적해 중첩 가능한 트리를 만든다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.roots = []          # 최상위 Table들
        self.table_stack = []
        self.row_stack = []
        self.cell_stack = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            t = Table()
            if self.cell_stack:
                self.cell_stack[-1].children.append(t)
            else:
                self.roots.append(t)
            self.table_stack.append(t)
        elif tag == "tr":
            if self.table_stack:
                r = Row()
                self.table_stack[-1].rows.append(r)
                self.row_stack.append(r)
        elif tag in CELL_TAGS:
            if self.row_stack:
                c = Cell(tag, attrs)
                self.row_stack[-1].cells.append(c)
                self.cell_stack.append(c)

    def handle_endtag(self, tag):
        if tag == "table" and self.table_stack:
            self.table_stack.pop()
        elif tag == "tr" and self.row_stack:
            self.row_stack.pop()
        elif tag in CELL_TAGS and self.cell_stack:
            self.cell_stack.pop()

    def handle_data(self, data):
        if self.cell_stack and data.strip():
            self.cell_stack[-1].text_parts.append(data)


def grid_columns(table: Table) -> tuple[int, list[int], bool]:
    """rowspan/colspan을 점유 행렬로 풀어 정규 열 수를 구한다.
    반환: (열 수, 각 행이 채운 칸 수, 모든 행이 동일 폭으로 해소되는지)."""
    occupied = {}  # (r, c) -> True : 위 행 rowspan이 흘러내린 칸
    ncols = 0
    row_fill = []
    for r, row in enumerate(table.rows):
        c = 0
        filled = 0
        for cell in row.cells:
            while (r, c) in occupied:
                c += 1
                filled += 1
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    occupied[(r + dr, c + dc)] = True
            c += cell.colspan
            filled += cell.colspan
        # 행 끝에 남은 rowspan 점유칸까지 포함
        while (r, c) in occupied:
            c += 1
            filled += 1
        row_fill.append(filled)
        ncols = max(ncols, c)
    consistent = len(set(row_fill)) <= 1 if row_fill else True
    return ncols, row_fill, consistent


def cell_to_node(cell: Cell) -> dict:
    if cell.children:
        # 우리 데이터는 셀당 중첩표 1개. 다수면 첫 표만 펼치고 나머지는 무시 경고.
        if len(cell.children) > 1:
            print(f"  ⚠ 셀에 중첩표 {len(cell.children)}개 — 첫 표만 반영")
        node = table_to_node(cell.children[0])
        node["col_span"] = cell.colspan
        node["row_span"] = cell.rowspan
        if cell.text:
            node["anchor"] = cell.text
        return node
    if not cell.text:
        ctype = "empty"
    elif cell.tag == "th":
        ctype = "label"
    else:
        ctype = "text"
    node = {"type": ctype, "col_span": cell.colspan, "row_span": cell.rowspan}
    if cell.text:
        node["text"] = cell.text
    return node


def table_to_node(table: Table) -> dict:
    ncols, row_fill, consistent = grid_columns(table)
    return {
        "type": "table",
        "columns": ncols,
        "row_count": len(table.rows),
        "col_normalized_consistent": consistent,
        "row_fill": row_fill,
        "rows": [{"cells": [cell_to_node(c) for c in row.cells]} for row in table.rows],
    }


def extract(html_path: Path) -> dict:
    p = TableTreeParser()
    p.feed(html_path.read_text(encoding="utf-8"))
    roots = [table_to_node(t) for t in p.roots]
    skeleton = roots[0] if len(roots) == 1 else roots
    return {"id": html_path.stem, "source": html_path.name, "skeleton": skeleton}


def main() -> None:
    GT.mkdir(exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = [HTML / f"{args[0]}.html"] if args else sorted(HTML.glob("*.html"))
    for f in files:
        data = extract(f)
        out = GT / f"{f.stem}.gt.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        sk = data["skeleton"]
        tables = sk if isinstance(sk, list) else [sk]
        cols = ", ".join(f"{t['columns']}열/{t['row_count']}행"
                         f"{'' if t['col_normalized_consistent'] else ' ⚠불일치'}"
                         for t in tables)
        print(f"✓ {out.name}  [{cols}]")


if __name__ == "__main__":
    main()
