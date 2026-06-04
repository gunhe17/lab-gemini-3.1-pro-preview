#!/usr/bin/env python3.12
"""colab_features.ipynb 생성 — PaddleOCR-VL-1.6 유용 기능 전반 테스트 on s6 (GPU).

우리에게 유효한 기능을 s6 한 장으로 두루 시험:
 ① 전체-페이지 파싱(full-page) → Markdown/JSON/print
 ② 레이아웃 검출(PP-DocLayout) 결과 요약
 ③ 표 구조 → HTML + 우리 TEDS-Struct 채점(vs 정답·Gemini 0.875 비교)
 ④ 출력 포맷(MD/JSON) 확인
GPU 경로(torch 제거 → paddle-gpu, 충돌 회피). 채점기·입력 내장(검증본).
생성: python3 make_colab_features.py
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
        "GEMINI_S6_HIGH = 0.875  # 우리 측정: Gemini 최고(3-flash) modal\n"
        "print('s6.png 작성, 정답 골격/기준선 로드 완료')\n"
    )

    install_cell = (
        "# === GPU 설치: torch 제거(충돌 원흉) → paddle-gpu. PaddleOCR-VL은 torch 불필요(검증) ===\n"
        "!pip uninstall -y torch torchvision torchaudio\n"
        "!pip -q install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/\n"
        "!pip -q install \"paddleocr[doc-parser]>=3.6.0\"\n"
        "import paddle; print('GPU 인식:', paddle.device.is_compiled_with_cuda())\n"
    )

    parse_cell = (
        "# === ① 전체-페이지 파싱 (full-page) → MD/JSON/print ===\n"
        "import os, glob, json\n"
        "os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'\n"
        "from paddleocr import PaddleOCRVL\n"
        "pipe = PaddleOCRVL(pipeline_version='v1.6')   # 최초 1회 모델(~2GB) 다운로드\n"
        "out = list(pipe.predict('s6.png'))            # GPU 추론(수십 초)\n"
        "for res in out:\n"
        "    res.save_to_markdown(save_path='out_md')   # ④ Markdown 출력\n"
        "    res.save_to_json(save_path='out_json')     # ④ JSON 출력(요소·bbox)\n"
        "print('저장 완료: out_md/, out_json/  · 결과 객체', len(out), '개')\n"
    )

    layout_cell = (
        "# === ② 레이아웃 검출 결과 요약 (PP-DocLayout) ===\n"
        "import glob, json\n"
        "from collections import Counter\n"
        "jf = (sorted(glob.glob('out_json/**/*.json', recursive=True)) + sorted(glob.glob('out_json*.json')))[0]\n"
        "d = json.load(open(jf, encoding='utf-8'))\n"
        "print('JSON 최상위 keys:', list(d.keys())[:25])\n"
        "# 레이아웃 블록 열거 (키 이름이 버전마다 다를 수 있어 방어적으로 탐색)\n"
        "blocks = None\n"
        "for k in ('parsing_res_list','layout_parsing_result','layout_det_res','res'):\n"
        "    v = d.get(k)\n"
        "    if isinstance(v, list) and v: blocks = v; print('블록 소스 key =', k); break\n"
        "    if isinstance(v, dict) and isinstance(v.get('boxes'), list): blocks = v['boxes']; print('블록 소스 key =', k+'.boxes'); break\n"
        "labels = Counter()\n"
        "for b in (blocks or []):\n"
        "    lab = (b.get('block_label') or b.get('label') or b.get('type') or b.get('cls') if isinstance(b, dict) else None)\n"
        "    if lab: labels[lab] += 1\n"
        "print('검출 요소 유형/개수:', dict(labels) or '(구조 상이 — 위 keys로 확인)')\n"
    )

    table_cell = (
        "# === ③ 표 구조 → HTML + 우리 TEDS-Struct 채점 ===\n"
        "import glob, re\n"
        "raw = ''\n"
        "for f in sorted(glob.glob('out_md/**/*.md', recursive=True)) + sorted(glob.glob('out_md*.md')):\n"
        "    raw = open(f, encoding='utf-8').read(); break\n"
        "print('--- Markdown 표 부분 ---')\n"
        "mt = re.search(r'<table.*</table>', raw, re.S | re.I)\n"
        "print((mt.group(0)[:500] if mt else raw[:500]))\n"
        "teds, skel = score_model_html(raw, GT['s6'])\n"
        "print('\\n>>> PaddleOCR-VL-1.6  s6 TEDS-Struct =', teds, ' (Gemini 최고', GEMINI_S6_HIGH, ')')\n"
        "print('--- normalized skeleton ---'); print(skel)\n"
        "results = {'PaddleOCR-VL-1.6 (GPU)': teds}\n"
    )

    summary_cell = (
        "# === ⑤ 요약 ===\n"
        "print('테스트한 기능:')\n"
        "print('  ① 전체-페이지 파싱  → out_md/ , out_json/')\n"
        "print('  ② 레이아웃 검출      → 위 요소 유형/개수')\n"
        "print('  ③ 표 구조→HTML + TEDS:', results)\n"
        "print('  ④ 출력 포맷 MD/JSON  → 저장 확인')\n"
        "print()\n"
        "print('해석: TEDS는 중첩 정답 기준이라 평탄 인코딩을 과소평가.')\n"
        "print('핵심은 표 윗줄을 [빈칸|내용|빈칸] 3칸으로 분리하는지(=Gemini가 병합한 빈칸 포착) — skeleton 확인.')\n"
    )

    nb = {
        "cells": [
            cell("# PaddleOCR-VL-1.6 기능 전반 테스트 on s6 (GPU)\n\n"
                 "우리에게 유효한 기능을 s6 한 장으로 시험: **①전체-페이지 파싱 ②레이아웃 검출 "
                 "③표→HTML+TEDS ④MD/JSON 출력**.\n\n"
                 "**런타임: GPU(T4) 필수.** 핵심은 **torch 제거** — paddle-gpu와 torch의 nccl 충돌(커널 사망) 회피. "
                 "PaddleOCR-VL은 torch 없이 동작. 채점기·입력은 repo 검증본 내장.\n\n"
                 "※ element-level(transformers 경로)은 torch가 필요해 이 GPU paddle 스택과 충돌 → 본 노트북에선 제외"
                 "(필요시 별도 런타임). full-page 파싱이 표 인식을 포함하므로 우리 목적엔 충분.", "markdown"),
            cell(data_cell),
            cell("# 채점기(skeletonize + TEDS-Struct) — 검증본\n" + SCORER + "\nprint('채점기 로드 완료')\n"),
            cell("## 설치 (GPU · torch 제거 → paddle-gpu)\n\n"
                 "설치 후 `import` 에러 시 **Runtime ▸ Restart session** 후 [데이터][채점기][이하] 재실행.", "markdown"),
            cell(install_cell),
            cell("## ① 전체-페이지 파싱 → MD/JSON", "markdown"),
            cell(parse_cell),
            cell("## ② 레이아웃 검출 결과", "markdown"),
            cell(layout_cell),
            cell("## ③ 표 구조 → HTML + TEDS 채점", "markdown"),
            cell(table_cell),
            cell("## ⑤ 요약", "markdown"),
            cell(summary_cell),
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                     "accelerator": "GPU", "colab": {"provenance": []}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    out = HERE / "colab_features.ipynb"
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {out.name}  ({len(out.read_text(encoding='utf-8')) // 1024} KB, {len(nb['cells'])} cells)")


if __name__ == "__main__":
    main()
