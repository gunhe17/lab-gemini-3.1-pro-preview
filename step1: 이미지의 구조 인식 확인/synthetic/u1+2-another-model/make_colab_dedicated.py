#!/usr/bin/env python3.12
"""colab_mineru.ipynb / colab_nanonets.ipynb 생성 — 전용 파서 2종을 s6로 테스트.

요구: 출력은 전부 print()로 터미널에(파일 저장 X) → 복사해 전달하기 쉽게.
둘 다 torch/transformers 기반(Colab GPU 네이티브와 정합, paddle 충돌 없음).
s6 PNG·정답 골격·검증된 채점기 내장 → 노트북이 TEDS·skeleton까지 직접 print.
생성: python3 make_colab_dedicated.py
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


def data_cell():
    gt_s6 = (GT / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
    return (
        "import base64\n"
        f"open('s6.png','wb').write(base64.b64decode({json.dumps(b64(PNG / 's6-p011clone.png'))}))\n"
        f"GT = {{'s6': {json.dumps(gt_s6)}}}\n"
        "GEMINI_BEST = 0.875  # 우리 측정 Gemini 최고(3-flash)\n"
        "print('s6.png 작성, 정답 골격/기준선 로드 완료')\n"
    )


def scorer_cell():
    return "# 채점기(skeletonize + TEDS-Struct) — repo 검증본\n" + SCORER + "\nprint('채점기 로드 완료')\n"


def write_nb(name, title, install_cell, run_cell):
    nb = {
        "cells": [
            cell(title, "markdown"),
            cell(data_cell()),
            cell(scorer_cell()),
            cell("## 설치 → 추론 (출력은 print)", "markdown"),
            cell(install_cell),
            cell(run_cell),
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                     "accelerator": "GPU", "colab": {"provenance": []}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    out = HERE / name
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {name}  ({len(out.read_text(encoding='utf-8')) // 1024} KB)")


# ── MinerU2.5-Pro ─────────────────────────────────────────────────────────────
MINERU_TITLE = (
    "# MinerU2.5-Pro on s6 (Colab GPU · print 출력)\n\n"
    "전용 파서 표본②. **런타임: GPU(T4).** torch/transformers 기반이라 paddle 충돌 없음.\n"
    "모든 결과는 **print()** 로 출력(파일 저장 X) — 마지막 RAW/TEDS/skeleton을 복사해 전달.\n"
    "채점기·입력은 repo 검증본 내장. 모델 호출부는 2026 최신 API 기준 best-effort."
)
MINERU_INSTALL = (
    "# transformers 백엔드 + mineru-vl-utils\n"
    "!pip -q install \"mineru-vl-utils[transformers]\" accelerate\n"
    "print('설치 완료')\n"
)
MINERU_RUN = (
    "# === MinerU2.5-Pro 추론 (print) ===\n"
    "from transformers import AutoProcessor, Qwen2VLForConditionalGeneration\n"
    "from PIL import Image\n"
    "from mineru_vl_utils import MinerUClient\n"
    "MID = 'opendatalab/MinerU2.5-Pro-2604-1.2B'\n"
    "model = Qwen2VLForConditionalGeneration.from_pretrained(MID, dtype='auto', device_map='auto')\n"
    "processor = AutoProcessor.from_pretrained(MID, use_fast=True)\n"
    "client = MinerUClient(backend='transformers', model=model, processor=processor, image_analysis=False)\n"
    "out = client.two_step_extract(Image.open('s6.png'))\n"
    "print('=== RAW two_step_extract ===')\n"
    "print(out)\n"
    "raw = str(out)\n"
    "teds, skel = score_model_html(raw, GT['s6'])\n"
    "print('\\n>>> MinerU2.5-Pro  s6 TEDS-Struct =', teds, ' (Gemini 최고', GEMINI_BEST, ')')\n"
    "print('=== normalized skeleton ===')\n"
    "print(skel)\n"
)

# ── Nanonets-OCR2-3B ──────────────────────────────────────────────────────────
NANO_TITLE = (
    "# Nanonets-OCR2-3B on s6 (Colab GPU · print 출력)\n\n"
    "전용 파서 표본③. 리더보드 'Nanonets OCR-3(93.3)'는 이 **OCR2-3B**로 추정 — "
    "정확한 다른 id 있으면 `MID`만 교체.\n\n"
    "**런타임: GPU(T4).** transformers 기반. 결과는 전부 **print()**. 채점기·입력 내장."
)
NANO_INSTALL = (
    "!pip -q install -U transformers accelerate\n"
    "print('설치 완료')\n"
)
NANO_RUN = (
    "# === Nanonets-OCR2-3B 추론 (print) — bf16(품질보존) + 이미지 안전축소로 T4 OOM 회피 ===\n"
    "# ※ 4bit(nf4)는 이 VLM 출력을 깨뜨림(랜덤토큰) → 쓰지 말 것. 원인은 'auto'=fp32(12GB) OOM이었음.\n"
    "import os, torch\n"
    "os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'\n"
    "from transformers import AutoModelForImageTextToText, AutoProcessor\n"
    "from PIL import Image\n"
    "MID = 'nanonets/Nanonets-OCR2-3B'\n"
    "model = AutoModelForImageTextToText.from_pretrained(MID, torch_dtype=torch.bfloat16, device_map='auto')\n"
    "proc = AutoProcessor.from_pretrained(MID)\n"
    "img = Image.open('s6.png').convert('RGB')\n"
    "if max(img.size) > 1400:   # T4 attention 메모리 보호(구조 인식엔 충분)\n"
    "    s = 1400 / max(img.size); img = img.resize((int(img.width*s), int(img.height*s)))\n"
    "prompt = ('Extract the text from the above document as if you were reading it naturally. '\n"
    "          'Return tables in HTML format. Return equations in LaTeX. '\n"
    "          'Use <img> tags for figures, and ☐/☑ for checkboxes.')\n"
    "messages = [{'role':'user','content':[{'type':'image','image':img},{'type':'text','text':prompt}]}]\n"
    "text = proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)\n"
    "inputs = proc(text=[text], images=[img], return_tensors='pt').to(model.device)\n"
    "gen = model.generate(**inputs, max_new_tokens=4000, do_sample=False)\n"
    "result = proc.batch_decode(gen[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]\n"
    "print('=== RAW output (앞 2000자) ===')\n"
    "print(result[:2000])\n"
    "teds, skel = score_model_html(result, GT['s6'])\n"
    "print('\\n>>> Nanonets-OCR2-3B  s6 TEDS-Struct =', teds, ' (Gemini 최고', GEMINI_BEST, ')')\n"
    "print('=== normalized skeleton ===')\n"
    "print(skel)\n"
)


def main():
    write_nb("colab_mineru.ipynb", MINERU_TITLE, MINERU_INSTALL, MINERU_RUN)
    write_nb("colab_nanonets.ipynb", NANO_TITLE, NANO_INSTALL, NANO_RUN)


if __name__ == "__main__":
    main()
