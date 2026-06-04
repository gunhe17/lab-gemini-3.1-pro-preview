#!/usr/bin/env python3.12
"""자체완결 Colab 노트북 생성기 — MinerU2.5 / PaddleOCR-VL 를 s6에 돌려 TEDS-Struct로 채점.

노트북에 내장: s6/s4 PNG(base64) · 정답 골격(GT) · 채점기(skeletonize+TEDS, 우리 repo와 동일).
채점기는 여기서 **우리 기존 점수와 일치하는지 검증**한 뒤 임베드한다. 모델 호출부는 GPU Colab용
best-effort(최신 패키지라 소폭 수정 필요할 수 있음). 사용자는 Colab에서 런타임=GPU로 실행.
생성: python3 make_colab.py  → colab_test.ipynb
"""
import base64
import json
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
PNG = SYN / "png"
GT = SYN / "gt"

# ── 채점기(self-contained): repo의 extract_gt/skeletonize/teds 를 노트북용으로 합본 ──────
SCORER = r'''
import re
from html.parser import HTMLParser
CELL_TAGS = {"td", "th"}

class Cell:
    def __init__(self, tag, attrs):
        self.tag = tag; self.attrs = dict(attrs); self.text_parts = []; self.children = []
    @property
    def colspan(self):
        try: return int(self.attrs.get("colspan", 1))
        except Exception: return 1
    @property
    def rowspan(self):
        try: return int(self.attrs.get("rowspan", 1))
        except Exception: return 1
    @property
    def text(self): return re.sub(r"\s+", " ", "".join(self.text_parts)).strip()

class Row:
    def __init__(self): self.cells = []
class Table:
    def __init__(self): self.rows = []

class TableTreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.roots = []; self.table_stack = []; self.row_stack = []; self.cell_stack = []
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            t = Table()
            (self.cell_stack[-1].children if self.cell_stack else self.roots).append(t)
            self.table_stack.append(t)
        elif tag == "tr":
            if self.table_stack:
                r = Row(); self.table_stack[-1].rows.append(r); self.row_stack.append(r)
        elif tag in CELL_TAGS:
            if self.row_stack:
                c = Cell(tag, attrs); self.row_stack[-1].cells.append(c); self.cell_stack.append(c)
    def handle_endtag(self, tag):
        if tag == "table" and self.table_stack: self.table_stack.pop()
        elif tag == "tr" and self.row_stack: self.row_stack.pop()
        elif tag in CELL_TAGS and self.cell_stack: self.cell_stack.pop()
    def handle_data(self, data):
        if self.cell_stack and data.strip(): self.cell_stack[-1].text_parts.append(data)

def _emit(table, indent):
    pad = "  " * indent
    out = [f"{pad}<table>"]
    for row in table.rows:
        out.append(f"{pad}  <tr>")
        for cell in row.cells:
            attr = ""
            if cell.colspan != 1: attr += f' colspan="{cell.colspan}"'
            if cell.rowspan != 1: attr += f' rowspan="{cell.rowspan}"'
            if cell.children:
                out.append(f"{pad}    <td{attr}>")
                for ch in cell.children: out.append(_emit(ch, indent + 3))
                out.append(f"{pad}    </td>")
            else:
                out.append(f"{pad}    <td{attr}></td>")
        out.append(f"{pad}  </tr>")
    out.append(f"{pad}</table>")
    return "\n".join(out)

def skeletonize(html_text):
    p = TableTreeParser(); p.feed(html_text)
    return "\n".join(_emit(t, 0) for t in p.roots)

class Node:
    __slots__ = ("label", "children")
    def __init__(self, label): self.label = label; self.children = []

def _table_to_tree(table):
    n = Node("table")
    for row in table.rows:
        rn = Node("tr")
        for cell in row.cells:
            cn = Node(f"td|{cell.colspan}|{cell.rowspan}")
            for ch in cell.children: cn.children.append(_table_to_tree(ch))
            rn.children.append(cn)
        n.children.append(rn)
    return n

def _html_to_tree(html_text):
    p = TableTreeParser(); p.feed(html_text)
    root = Node("doc")
    for t in p.roots: root.children.append(_table_to_tree(t))
    return root

def _postorder(root):
    order = []
    def rec(n):
        for c in n.children: rec(c)
        order.append(n)
    rec(root)
    pid = {id(n): i for i, n in enumerate(order)}
    def leftmost(n):
        while n.children: n = n.children[0]
        return n
    l = [pid[id(leftmost(n))] for n in order]
    last = {}
    for i in range(len(order)): last[l[i]] = i
    return order, l, sorted(last.values())

def _ted(A, B):
    ao, al, akr = _postorder(A); bo, bl, bkr = _postorder(B)
    n, m = len(ao), len(bo)
    td = [[0] * m for _ in range(n)]
    for i in akr:
        for j in bkr:
            li, lj = al[i], bl[j]
            fd = {(li - 1, lj - 1): 0}
            for di in range(li, i + 1): fd[(di, lj - 1)] = fd[(di - 1, lj - 1)] + 1
            for dj in range(lj, j + 1): fd[(li - 1, dj)] = fd[(li - 1, dj - 1)] + 1
            for di in range(li, i + 1):
                for dj in range(lj, j + 1):
                    if al[di] == li and bl[dj] == lj:
                        cost = 0 if ao[di].label == bo[dj].label else 1
                        fd[(di, dj)] = min(fd[(di - 1, dj)] + 1, fd[(di, dj - 1)] + 1, fd[(di - 1, dj - 1)] + cost)
                        td[di][dj] = fd[(di, dj)]
                    else:
                        fd[(di, dj)] = min(fd[(di - 1, dj)] + 1, fd[(di, dj - 1)] + 1, fd[(al[di] - 1, bl[dj] - 1)] + td[di][dj])
    return td[n - 1][m - 1]

def _size(r): return 1 + sum(_size(c) for c in r.children)

def teds_struct_html(pred_html, gt_html):
    a, b = _html_to_tree(pred_html), _html_to_tree(gt_html)
    denom = max(_size(a), _size(b))
    return 1.0 - _ted(a, b) / denom if denom else 1.0

def score_model_html(raw_text, gt_skeleton):
    """모델의 원문(markdown/html)에서 표를 뽑아 골격화 → 정답 골격과 TEDS-Struct."""
    m = re.search(r"<table.*</table>", raw_text or "", re.S | re.I)
    if not m:
        return None, "(원문에 <table>...</table> 없음 — markdown 파이프표일 수 있음. raw 확인)"
    skel = skeletonize(m.group(0))
    return teds_struct_html(skel, gt_skeleton), skel
'''


def b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()


def validate_scorer():
    ns = {}
    exec(SCORER, ns)
    gt_s6 = (GT / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
    rec = json.loads((SYN / "u1" / "v2.1" / "s6-p011clone.high.json").read_text(encoding="utf-8"))
    pred = rec["modal_skeleton"]
    got = ns["teds_struct_html"](pred, gt_s6)
    exp = rec["modal_teds"]
    assert abs(got - exp) < 1e-6, f"scorer mismatch: got {got} vs expected {exp}"
    # self-similarity = 1.0
    assert abs(ns["teds_struct_html"](gt_s6, gt_s6) - 1.0) < 1e-9
    print(f"  채점기 검증 OK: s6 high modal TEDS={got:.4f} (기록 {exp:.4f}) · self=1.0")


def cell(src, kind="code"):
    return {"cell_type": kind, "metadata": {}, "source": src,
            **({"outputs": [], "execution_count": None} if kind == "code" else {})}


def main():
    validate_scorer()
    gt_s6 = (GT / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
    gt_s4 = (GT / "s4-nested-asym.skeleton.html").read_text(encoding="utf-8")

    data_cell = (
        "# 입력(s6/s4 PNG) + 정답 골격 — 노트북에 내장(외부 의존 없음)\n"
        "import base64\n"
        f"S6_PNG_B64 = {json.dumps(b64(PNG / 's6-p011clone.png'))}\n"
        f"S4_PNG_B64 = {json.dumps(b64(PNG / 's4-nested-asym.png'))}\n"
        "open('s6.png','wb').write(base64.b64decode(S6_PNG_B64))\n"
        "open('s4.png','wb').write(base64.b64decode(S4_PNG_B64))\n"
        f"GT = {{'s6': {json.dumps(gt_s6)}, 's4': {json.dumps(gt_s4)}}}\n"
        "print('입력 s6.png/s4.png 작성, 정답 골격 GT 로드 완료')\n"
    )

    baseline_md = (
        "## 기준선 — Gemini (우리 측정, s6 high · n=5)\n"
        "| 모델 | s6 high TEDS-Struct |\n|---|---|\n"
        "| gemini-3.1-pro (현재) | 0.850 ± 0.050 |\n"
        "| gemini-3-flash | **0.875 ± 0.000** |\n"
        "| gemini-3.5-flash | 0.815 ± 0.138 |\n\n"
        "**목표 질문:** 전용 파서(MinerU2.5 / PaddleOCR-VL)가 이 0.875 천장(빈칸 격자선 누락)을 넘는가? "
        "s4(합성 L4 중첩)는 대조 — Gemini는 모두 1.000."
    )

    mineru_cell = (
        "# === MinerU 2.5 (VLM, transformers 백엔드) ===\n"
        "# Colab: 런타임 > 런타임 유형 변경 > GPU(T4) 필수. 최초 가중치 다운로드 ~수 GB.\n"
        "# MinerU2.5-Pro 가중치를 쓰려면 HF repo 지정이 필요할 수 있음(기본 CLI는 2.5).\n"
        "!pip -q install -U \"mineru[core]\" || pip -q install -U mineru\n"
        "import os, glob, json as _json\n"
        "os.system('mineru -p s6.png -o mineru_out -b vlm-transformers')\n"
        "raw = ''\n"
        "for f in sorted(glob.glob('mineru_out/**/*.md', recursive=True)):\n"
        "    raw = open(f, encoding='utf-8').read(); break\n"
        "if '<table' not in raw:  # 마크다운에 표 HTML이 없으면 content_list json에서\n"
        "    for f in glob.glob('mineru_out/**/*content_list*.json', recursive=True):\n"
        "        for b in _json.load(open(f, encoding='utf-8')):\n"
        "            for k in ('table_body','html','table'):\n"
        "                if isinstance(b.get(k), str) and '<table' in b[k]: raw += b[k]\n"
        "print('--- MinerU raw(앞 400자) ---'); print(raw[:400])\n"
        "teds, skel = score_model_html(raw, GT['s6'])\n"
        "print('\\n>>> MinerU2.5  s6 TEDS-Struct =', teds)\n"
        "results['MinerU2.5'] = teds\n"
    )

    paddle_install_cell = (
        "# === PaddleOCR-VL (0.9B) — 설치 ===\n"
        "# paddle 3.x GPU 휠은 paddle 공식 인덱스에서(PyPI엔 2.6.x뿐). paddleocr는 PyPI에서 별도 줄로.\n"
        "!pip -q install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/\n"
        "!pip -q install \"paddleocr[doc-parser]>=3.6.0\"\n"
        "# torch와 paddle이 서로 다른 nccl 버전을 핀(torch 2.28.9 vs paddle 2.25.1). 단일 GPU 추론엔 nccl 기능\n"
        "# 미사용 + paddle은 자체 번들 CUDA 사용 → torch가 요구하는 정확한 버전으로 맞추면 둘 다 import/동작.\n"
        "# ※ 버전은 Colab torch가 바뀌면 달라짐: 에러 메시지의 'torch ... requires nvidia-... ==X' 값으로 교체.\n"
        "!pip -q install nvidia-nccl-cu12==2.28.9 nvidia-cudnn-cu12==9.19.0.56 nvidia-cusparselt-cu12==0.7.1\n"
        "print('설치 완료. ⚠ Runtime ▸ Restart session 후 [데이터][채점기][아래 추론] 셀만 재실행(설치 줄 건너뜀).')\n"
    )

    paddle_run_cell = (
        "# === PaddleOCR-VL — 추론 + 채점 (재시작했다면 위 [데이터][채점기] 셀 먼저 실행) ===\n"
        "# PaddleOCR-VL-1.6 강제하려면 모델 인자/HF 지정이 필요할 수 있음(기본=최신 VL).\n"
        "import glob\n"
        "from paddleocr import PaddleOCRVL\n"
        "pipe = PaddleOCRVL()\n"
        "res = pipe.predict('s6.png')\n"
        "res[0].save_to_markdown('pp_out')\n"
        "raw = ''\n"
        "for f in sorted(glob.glob('pp_out*/**/*.md', recursive=True)) + sorted(glob.glob('pp_out*.md')) + sorted(glob.glob('pp_out/**/*.md', recursive=True)):\n"
        "    raw = open(f, encoding='utf-8').read(); break\n"
        "print('--- PaddleOCR-VL raw(앞 400자) ---'); print(raw[:400])\n"
        "teds, skel = score_model_html(raw, GT['s6'])\n"
        "print('\\n>>> PaddleOCR-VL  s6 TEDS-Struct =', teds)\n"
        "results['PaddleOCR-VL'] = teds\n"
    )

    summary_cell = (
        "# === 종합 ===\n"
        "base = {'gemini-3.1-pro': 0.850, 'gemini-3-flash': 0.875, 'gemini-3.5-flash': 0.815}\n"
        "print('s6 TEDS-Struct 비교 (높을수록 좋음, 0.875=Gemini 최고 천장)')\n"
        "for k, v in {**base, **results}.items():\n"
        "    mark = ''\n"
        "    if isinstance(v, float):\n"
        "        mark = '  ← 천장 돌파!' if v > 0.8751 else ('  ← 동률' if abs(v-0.875)<1e-3 else '')\n"
        "    print(f'  {k:18} {v if v is not None else \"실패\"}{mark}')\n"
        "print('\\n해석: 전용 파서가 0.875를 분명히 넘으면 → 빈칸 격자선을 본다 = 교체/하이브리드 정당.')\n"
    )

    nb = {
        "cells": [
            cell("# u1+u2 — 전용 파서 비교 (MinerU2.5 / PaddleOCR-VL) on s6\n\n"
                 "Gemini가 못 뚫은 **s6 0.875 천장**(중첩표 빈칸 격자선 누락)을 전용 문서 파서가 넘는지 검증.\n\n"
                 "**실행 전: 런타임 > 런타임 유형 변경 > 하드웨어 가속기 = GPU(T4).**\n\n"
                 "채점은 우리 repo와 동일한 TEDS-Struct(구조 트리편집 유사도, 1.0=완벽). "
                 "모델 호출부는 최신 패키지 기준 best-effort라, 패키지 API가 바뀌었으면 해당 셀만 소폭 수정.", "markdown"),
            cell(data_cell),
            cell("# 채점기(skeletonize + TEDS-Struct) — repo와 동일, 로컬 검증 통과본\n"
                 + SCORER + "\nresults = {}\nprint('채점기 로드 완료')\n"),
            cell(baseline_md, "markdown"),
            cell("## 1) MinerU 2.5\n\n"
                 "⚠ **두 모델은 각자 fresh 런타임에서 실행.** MinerU(vLLM/torch)와 PaddleOCR(paddle)의 "
                 "torch/CUDA 의존성이 충돌합니다. MinerU를 먼저 끝내고 점수를 기록한 뒤, "
                 "**Runtime ▸ Disconnect and delete runtime → 재연결 → [데이터][채점기] 재실행 → PaddleOCR 섹션**으로.", "markdown"),
            cell(mineru_cell),
            cell("## 2) PaddleOCR-VL\n\n"
                 "위 안내대로 **새 런타임**에서 [데이터][채점기] 실행 후 아래 설치→추론.\n"
                 "설치 후 `import` 가 `ncclCommShrink` 로 실패하면 **Runtime ▸ Restart session** 후 "
                 "[데이터][채점기][추론] 셀만 재실행(설치 줄은 이미 적용됨).", "markdown"),
            cell(paddle_install_cell),
            cell(paddle_run_cell),
            cell("## 3) 종합 비교\n\n두 모델 점수가 `results`에 모이면 실행. (각 모델을 별도 런타임에서 돌렸다면 "
                 "숫자를 직접 적어 비교해도 됨.)", "markdown"),
            cell(summary_cell),
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                     "accelerator": "GPU", "colab": {"provenance": []}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    out = HERE / "colab_test.ipynb"
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    kb = len(out.read_text(encoding="utf-8")) // 1024
    print(f"✓ {out.name}  ({kb} KB, {len(nb['cells'])} cells)")


if __name__ == "__main__":
    main()
