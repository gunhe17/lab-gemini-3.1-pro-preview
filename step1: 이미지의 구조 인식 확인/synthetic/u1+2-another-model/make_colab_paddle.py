#!/usr/bin/env python3.12
"""colab_paddle.ipynb 생성 — 로컬에서 동작한 'CPU paddle' 구성을 Colab에 그대로.

로컬 M1에서 paddlepaddle(CPU)+paddleocr[doc-parser]+PaddleOCRVL 적재까지 성공했고 8GB RAM만
모자랐다. Colab(~12GB RAM)은 그 OOM을 넘긴다. CPU paddle은 CUDA 미사용 → torch/nccl 충돌 없음
(앞서 커널을 죽인 paddle-gpu 충돌이 원천 제거). GPU 불필요·표준 런타임 OK·CPU라 수 분 소요.
생성: python3 make_colab_paddle.py
"""
import base64
import json
from pathlib import Path

from make_colab import SCORER  # 로컬 검증 통과한 동일 채점기 재사용

HERE = Path(__file__).parent
SYN = HERE.parent
PNG = SYN / "png"
GT = SYN / "gt"


def b64(p):
    return base64.b64encode(p.read_bytes()).decode()


def cell(src, kind="code"):
    return {"cell_type": kind, "metadata": {}, "source": src,
            **({"outputs": [], "execution_count": None} if kind == "code" else {})}


def main():
    gt_s6 = (GT / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")

    data_cell = (
        "import base64\n"
        f"open('s6.png','wb').write(base64.b64decode({json.dumps(b64(PNG / 's6-p011clone.png'))}))\n"
        f"GT = {{'s6': {json.dumps(gt_s6)}}}\n"
        "print('s6.png 작성, 정답 골격 GT 로드 완료')\n"
    )

    install_cell = (
        "# === 설치: CPU paddle (로컬에서 동작한 구성). paddle-gpu 안 씀 → torch/CUDA 충돌 없음 ===\n"
        "# GPU 불필요. 표준 런타임(CPU)으로 충분하고, Colab RAM(~12GB)이 로컬 8GB OOM을 넘긴다.\n"
        "!pip -q install paddlepaddle \"paddleocr[doc-parser]\"\n"
        "print('설치 완료')\n"
    )

    run_cell = (
        "# === PaddleOCR-VL-1.6 (CPU) 추론 + 채점 ===\n"
        "import os, glob, re\n"
        "os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'\n"
        "from paddleocr import PaddleOCRVL\n"
        "pipe = PaddleOCRVL()              # 최초 1회 모델(~2GB) 다운로드\n"
        "res = pipe.predict('s6.png')      # CPU 추론 — 수 분 소요 가능\n"
        "raw = ''\n"
        "for r in res:\n"
        "    try: r.save_to_markdown(save_path='pp_out')\n"
        "    except Exception as e: print('save warn:', e)\n"
        "for f in sorted(glob.glob('pp_out/**/*.md', recursive=True)) + sorted(glob.glob('pp_out*.md')):\n"
        "    raw = open(f, encoding='utf-8').read(); break\n"
        "print('--- RAW HEAD (600자) ---'); print(raw[:600])\n"
        "teds, skel = score_model_html(raw, GT['s6'])\n"
        "print('\\n>>> PaddleOCR-VL-1.6 (Colab CPU)  s6 TEDS-Struct =', teds)\n"
        "print('--- normalized skeleton ---'); print(skel)\n"
    )

    nb = {
        "cells": [
            cell("# PaddleOCR-VL-1.6 on Colab (CPU paddle — 로컬 검증 구성)\n\n"
                 "로컬 M1에서 적재까지 성공·8GB RAM만 부족했던 그 구성을 Colab(~12GB RAM)에서 그대로 실행.\n\n"
                 "**런타임: 표준(CPU)으로 충분.** GPU 불필요(오히려 paddle-gpu는 torch와 CUDA 충돌로 커널이 죽었음).\n"
                 "채점기는 repo와 동일(로컬에서 s6 modal TEDS=0.875 일치 검증).", "markdown"),
            cell(data_cell),
            cell("# 채점기(skeletonize + TEDS-Struct) — 검증본\n" + SCORER + "\nprint('채점기 로드 완료')\n"),
            cell("## 설치 → 추론", "markdown"),
            cell(install_cell),
            cell(run_cell),
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                     "colab": {"provenance": []}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    out = HERE / "colab_paddle.ipynb"
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {out.name}  ({len(out.read_text(encoding='utf-8')) // 1024} KB, {len(nb['cells'])} cells)")


if __name__ == "__main__":
    main()
