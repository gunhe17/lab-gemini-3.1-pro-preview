#!/usr/bin/env python3.12
"""TEDS-Struct 채점기 (Tree-Edit-Distance-based Similarity, 구조 전용).

표 HTML을 트리로 보고 트리 편집거리로 유사도를 잰다.
  TEDS = 1 - EditDist(예측, 정답) / max(|예측|, |정답|)
구조 전용이라 텍스트는 무시하고 태그+colspan·rowspan만 비교(skeletonize 출력 전제).
편집거리는 Zhang-Shasha 알고리즘(삽입·삭제=1, 치환=라벨 같으면 0 아니면 1).

비교 노드 라벨:
  table / tr / td|<colspan>|<rowspan>   ← td는 병합 수치까지 라벨에 포함
th/td는 skeletonize에서 이미 td로 통일됨.

사용(모듈):  from teds import teds_struct_html;  teds_struct_html(pred_html, gt_html) -> float
사용(CLI) :  python3.12 teds.py            # gt/*.skeleton.html 자가검증 매트릭스
             python3.12 teds.py A.html B.html   # 두 HTML 점수
"""
import sys
from pathlib import Path

from extract_gt import TableTreeParser, Table

HERE = Path(__file__).parent
GT = HERE / "gt"


class Node:
    __slots__ = ("label", "children")

    def __init__(self, label):
        self.label = label
        self.children = []


def table_to_tree(table: Table) -> Node:
    n = Node("table")
    for row in table.rows:
        rn = Node("tr")
        for cell in row.cells:
            cn = Node(f"td|{cell.colspan}|{cell.rowspan}")
            for child in cell.children:
                cn.children.append(table_to_tree(child))
            rn.children.append(cn)
        n.children.append(rn)
    return n


def html_to_tree(html_text: str) -> Node:
    p = TableTreeParser()
    p.feed(html_text)
    root = Node("doc")  # 루트 표가 여럿일 수 있어 doc로 감쌈
    for t in p.roots:
        root.children.append(table_to_tree(t))
    return root


def _postorder(root: Node):
    """후위순회 노드 리스트 + 각 노드의 최좌단 잎 후위인덱스(l) + keyroots."""
    order = []

    def rec(n):
        for c in n.children:
            rec(c)
        order.append(n)

    rec(root)
    pid = {id(n): i for i, n in enumerate(order)}

    def leftmost(n):
        while n.children:
            n = n.children[0]
        return n

    l = [pid[id(leftmost(n))] for n in order]
    # keyroots: 각 l값마다 가장 큰 후위인덱스
    last = {}
    for i in range(len(order)):
        last[l[i]] = i
    keyroots = sorted(last.values())
    return order, l, keyroots


def tree_edit_distance(A: Node, B: Node) -> int:
    ao, al, akr = _postorder(A)
    bo, bl, bkr = _postorder(B)
    n, m = len(ao), len(bo)
    td = [[0] * m for _ in range(n)]
    for i in akr:
        for j in bkr:
            li, lj = al[i], bl[j]
            # 포레스트 거리 fd, 인덱스 -1 오프셋 위해 dict 사용
            fd = {(li - 1, lj - 1): 0}
            for di in range(li, i + 1):
                fd[(di, lj - 1)] = fd[(di - 1, lj - 1)] + 1
            for dj in range(lj, j + 1):
                fd[(li - 1, dj)] = fd[(li - 1, dj - 1)] + 1
            for di in range(li, i + 1):
                for dj in range(lj, j + 1):
                    if al[di] == li and bl[dj] == lj:
                        cost = 0 if ao[di].label == bo[dj].label else 1
                        fd[(di, dj)] = min(
                            fd[(di - 1, dj)] + 1,
                            fd[(di, dj - 1)] + 1,
                            fd[(di - 1, dj - 1)] + cost,
                        )
                        td[di][dj] = fd[(di, dj)]
                    else:
                        fd[(di, dj)] = min(
                            fd[(di - 1, dj)] + 1,
                            fd[(di, dj - 1)] + 1,
                            fd[(al[di] - 1, bl[dj] - 1)] + td[di][dj],
                        )
    return td[n - 1][m - 1]


def _size(root: Node) -> int:
    return 1 + sum(_size(c) for c in root.children)


def teds_struct_tree(pred: Node, gt: Node) -> float:
    dist = tree_edit_distance(pred, gt)
    denom = max(_size(pred), _size(gt))
    return 1.0 - dist / denom if denom else 1.0


def teds_struct_html(pred_html: str, gt_html: str) -> float:
    return teds_struct_tree(html_to_tree(pred_html), html_to_tree(gt_html))


def _self_check() -> None:
    files = sorted(GT.glob("*.skeleton.html"))
    if not files:
        sys.exit("gt/*.skeleton.html 없음 — 먼저 skeletonize.py 실행")
    trees = {f.stem.replace(".skeleton", ""): html_to_tree(f.read_text(encoding="utf-8")) for f in files}
    ids = list(trees)
    print("자가검증: 대각(자기유사)=1.000 이어야 하고, 비대각<1 이면 변별력 OK\n")
    print("           " + "  ".join(f"{i[:7]:>7}" for i in ids))
    for a in ids:
        row = []
        for b in ids:
            s = teds_struct_tree(trees[a], trees[b])
            row.append(f"{s:7.3f}")
        print(f"{a[:10]:>10} " + "  ".join(row))
    # 섭동 테스트: s2에서 colspan 하나를 망가뜨리면 점수 하락하는지
    base = trees["s2-multihead"]
    broken = html_to_tree(
        (GT / "s2-multihead.skeleton.html").read_text(encoding="utf-8").replace('colspan="2"', "", 1)
    )
    print(f"\n섭동 테스트(s2 colspan 1개 제거): TEDS={teds_struct_tree(broken, base):.3f} (1.0 미만이면 정상)")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) == 2:
        a = Path(args[0]).read_text(encoding="utf-8")
        b = Path(args[1]).read_text(encoding="utf-8")
        print(f"TEDS-Struct = {teds_struct_html(a, b):.4f}")
    else:
        _self_check()


if __name__ == "__main__":
    main()
