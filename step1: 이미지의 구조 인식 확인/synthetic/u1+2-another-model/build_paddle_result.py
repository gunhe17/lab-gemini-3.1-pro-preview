#!/usr/bin/env python3
"""PaddleOCR-VL-1.6 s6 결과를 flash/flash35와 동일 스키마로 paddle/ 폴더에 정리.

원천: paddle_s6_raw.html(호스티드/CPU/GPU/Space 5경로 동일 출력). 골격·TEDS는 우리 채점기로 derive.
출력: paddle/u1_s6-p011clone.json (flash 스키마 + paddle 전용 필드)
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize
from teds import teds_struct_html

GT = (SYN / "gt" / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
raw = (HERE / "paddle_s6_raw.html").read_text(encoding="utf-8")
m = re.search(r"<table.*</table>", raw, re.S | re.I)
skel = skeletonize(m.group(0))
teds = round(teds_struct_html(skel, GT), 5)

PATHS = ["hosted demo", "local M1 CPU(적재)", "Colab CPU", "Colab GPU(features)", "HF Space gradio_client"]

rec = {
    "model": "PaddleOCR-VL-1.6",
    "page": "s6-p011clone",
    "mr": "native",                 # PaddleOCR 자체 해상도 처리(Gemini의 media_resolution과 다름)
    "n": 1,                          # 결정론적 단일 출력 (n=5 샘플링 아님)
    "teds_mean": teds, "teds_std": 0.0, "teds_min": teds, "teds_max": teds,
    "scores": [teds],
    "modal_teds": teds, "agreement": 1.0, "distinct": 1,
    "modal_skeleton": skel,
    # ── paddle 전용 ──
    "encoding": "flat (colspan/rowspan, 9열)",
    "perception_empty_cells": "정확 — [빈칸|내용|빈칸] 3칸 분리 (Gemini가 병합한 빈칸 포착)",
    "layout_detection": "{table:1, paragraph_title:2, text:6}",
    "reproduced_paths": PATHS,
    "note": "나이브 TEDS는 중첩 GT 기준이라 평탄 인코딩을 과소평가. 격자 자체는 정답과 동치(평탄화 시 일치).",
    "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
}

out = HERE / "paddle" / "u1_s6-p011clone.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✓ paddle/u1_s6-p011clone.json  (TEDS={teds}, {len(PATHS)}경로 재현)")
