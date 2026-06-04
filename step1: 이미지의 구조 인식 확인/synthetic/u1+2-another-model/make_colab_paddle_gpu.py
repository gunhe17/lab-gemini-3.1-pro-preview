#!/usr/bin/env python3.12
"""colab_paddle_gpu.ipynb 생성 — GPU 경로(빠름). torch 제거로 충돌 회피.

CPU paddle은 동작하지만 자기회귀 생성이 느림(12분+). GPU(T4)면 수십 초.
앞서 Colab GPU 크래시 원흉 = paddle-gpu가 torch의 nccl을 깨뜨림. 그러나 PaddleOCR-VL은
torch가 필요 없음(로컬 .venv-ocr에 torch 미설치인데 정상 동작 확인) → torch를 제거하면
충돌 상대가 사라져 paddle-gpu가 자체 CUDA로 깔끔히 GPU 추론.
생성: python3 make_colab_paddle_gpu.py
"""
import base64
import json
from pathlib import Path

from make_colab import SCORER

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
        "print('s6.png 작성, GT 로드 완료')\n"
    )
    install_cell = (
        "# === GPU 경로: torch 제거(충돌 원흉) 후 paddle-gpu 설치 ===\n"
        "# PaddleOCR-VL은 torch 불필요(로컬 검증). Colab 기본 torch를 지우면 nccl 충돌 상대가 사라진다.\n"
        "!pip uninstall -y torch torchvision torchaudio\n"
        "!pip -q install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/\n"
        "!pip -q install \"paddleocr[doc-parser]\"\n"
        "import paddle; print('GPU 인식:', paddle.device.is_compiled_with_cuda(), '· 설치 완료')\n"
    )
    run_cell = (
        "# === PaddleOCR-VL-1.6 (GPU) 추론 + 채점 ===\n"
        "import os, glob, re\n"
        "os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'\n"
        "from paddleocr import PaddleOCRVL\n"
        "pipe = PaddleOCRVL()              # paddle-gpu면 GPU 자동 사용\n"
        "res = pipe.predict('s6.png')      # GPU 추론 — 수십 초\n"
        "raw = ''\n"
        "for r in res:\n"
        "    try: r.save_to_markdown(save_path='pp_out')\n"
        "    except Exception as e: print('save warn:', e)\n"
        "for f in sorted(glob.glob('pp_out/**/*.md', recursive=True)) + sorted(glob.glob('pp_out*.md')):\n"
        "    raw = open(f, encoding='utf-8').read(); break\n"
        "print('--- RAW HEAD (600자) ---'); print(raw[:600])\n"
        "teds, skel = score_model_html(raw, GT['s6'])\n"
        "print('\\n>>> PaddleOCR-VL-1.6 (Colab GPU)  s6 TEDS-Struct =', teds)\n"
        "print('--- normalized skeleton ---'); print(skel)\n"
    )
    nb = {
        "cells": [
            cell("# PaddleOCR-VL-1.6 on Colab **GPU** (빠름)\n\n"
                 "CPU는 자기회귀 생성이 느림(12분+). GPU면 수십 초.\n\n"
                 "**런타임: GPU(T4) 필수.** 핵심은 **torch 제거** — 앞서 커널을 죽인 충돌(paddle-gpu가 torch의 nccl을 깸)의\n"
                 "원흉을 없앤다. PaddleOCR-VL은 torch 없이 동작함(로컬 검증). 채점기는 repo와 동일(검증본).", "markdown"),
            cell(data_cell),
            cell("# 채점기(skeletonize + TEDS-Struct) — 검증본\n" + SCORER + "\nprint('채점기 로드 완료')\n"),
            cell("## 설치(torch 제거 → paddle-gpu) → 추론\n\n"
                 "설치 후 혹시 `import` 단계 에러가 나면 **Runtime ▸ Restart session** 후 "
                 "[데이터][채점기][추론]만 재실행(설치 줄은 이미 적용됨).", "markdown"),
            cell(install_cell),
            cell(run_cell),
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                     "accelerator": "GPU", "colab": {"provenance": []}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    out = HERE / "colab_paddle_gpu.ipynb"
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {out.name}  ({len(out.read_text(encoding='utf-8')) // 1024} KB, {len(nb['cells'])} cells)")


if __name__ == "__main__":
    main()
