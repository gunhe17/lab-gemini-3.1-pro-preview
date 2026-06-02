#!/usr/bin/env python3.12
"""순수 측정값만 추출 (판정·해석 없음).

outputs/p-NNN.skeleton.json → outputs/_measurements.json
필드: 선언 열수, 행별 폭(colspan 합), 행폭 최빈/최빈비율, 셀 타입 분포,
      표(노드) 수, 최대 중첩 깊이, 총 셀 수, usage.
"""
import json
import glob
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "outputs"
ORDER = ["p-038", "p-005", "p-011", "p-017", "p-007"]


def get_table(parsed):
    t = parsed[0] if isinstance(parsed, list) else parsed
    if isinstance(t, dict) and "tables" in t:
        t = t["tables"][0]
    return t


def cspan(c):
    v = c.get("colspan", 1)
    return v if isinstance(v, int) else 1


def row_widths(t):
    for k in ("rows", "structure"):
        v = t.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict) and "cells" in v[0]:
            return [sum(cspan(c) for c in r.get("cells", [])) for r in v]
    cells = t.get("cells")
    if isinstance(cells, list) and cells and "row" in cells[0]:
        g = defaultdict(int)
        for c in cells:
            g[c.get("row")] += cspan(c)
        return [g[k] for k in sorted(g)]
    return None


def type_counts(node, c):
    if isinstance(node, dict):
        for tk in ("type", "content_type", "kind"):
            v = node.get(tk)
            if isinstance(v, str):
                c[v] += 1
                break
        for v in node.values():
            type_counts(v, c)
    elif isinstance(node, list):
        for v in node:
            type_counts(v, c)


def max_depth(node, d=0):
    best = d
    if isinstance(node, dict):
        is_table = any(node.get(k) == "table" for k in ("type", "kind")) or "rows" in node or "structure" in node
        nd = d + 1 if is_table else d
        for v in node.values():
            best = max(best, max_depth(v, nd))
    elif isinstance(node, list):
        for v in node:
            best = max(best, max_depth(v, d))
    return best


def count_cells(node):
    n = 0
    if isinstance(node, dict):
        if any(k in node for k in ("content", "text", "content_label", "content_type")) and "rows" not in node:
            n += 1
        for v in node.values():
            n += count_cells(v)
    elif isinstance(node, list):
        for v in node:
            n += count_cells(v)
    return n


def main():
    res = {}
    for pid in ORDER:
        raw = json.load(open(OUT / f"{pid}.skeleton.json"))
        d = raw["parsed"]
        t = get_table(d)
        decl = t.get("columns")
        if isinstance(decl, str):
            decl = len(decl.split("|"))
        w = row_widths(t)
        dist = Counter(w) if w else {}
        mode = max(dist, key=dist.get) if dist else None
        tc = Counter()
        type_counts(d, tc)
        res[pid] = {
            "declared_columns": decl,
            "n_rows": len(w) if w else None,
            "row_widths": w,
            "row_width_dist": dict(dist),
            "row_width_mode": mode,
            "row_width_mode_ratio": round(dist.get(mode, 0) / len(w), 3) if w else None,
            "cell_type_counts": dict(tc),
            "table_nodes": tc.get("table", 0),
            "max_nesting_depth": max_depth(d),
            "total_cells": count_cells(d),
            "usage_total_tokens": raw.get("usage", {}).get("total_tokens"),
            "usage_cost_usd": raw.get("usage", {}).get("cost"),
        }
        print(f"{pid}: cols={decl} rows={res[pid]['n_rows']} widths={w} "
              f"types={dict(tc)} depth={res[pid]['max_nesting_depth']}")
    json.dump(res, open(OUT / "_measurements.json", "w"), ensure_ascii=False, indent=2)
    print("\n→ outputs/_measurements.json")


if __name__ == "__main__":
    main()
