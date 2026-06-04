#!/usr/bin/env python3
"""MinerU2.5-Pro s6 결과를 flash/paddle와 동일 스키마로 mineru/ 폴더에 정리.

원천: mineru/mineru_s6_raw.html (Colab GPU two_step_extract 출력). 골격·TEDS는 우리 채점기로 derive.
출력: mineru/u1_s6-p011clone.json
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
raw = (HERE / "mineru" / "mineru_s6_raw.html").read_text(encoding="utf-8")
m = re.search(r"<table.*</table>", raw, re.S | re.I)
skel = skeletonize(m.group(0))
teds = round(teds_struct_html(skel, GT), 5)

rec = {
    "model": "MinerU2.5-Pro (opendatalab/MinerU2.5-Pro-2604-1.2B)",
    "page": "s6-p011clone",
    "mr": "native", "n": 1,
    "teds_mean": teds, "teds_std": 0.0, "teds_min": teds, "teds_max": teds,
    "scores": [teds], "modal_teds": teds, "agreement": 1.0, "distinct": 1,
    "modal_skeleton": skel,
    "encoding": "flat (colspan/rowspan, 9열)",
    "perception_empty_cells": "부분 — 상단 본문 행은 [빈|내용|빈] 분리하나, rowspan(3/2) 불일치",
    "errors": "표 아래 '② 서비스 제공절차' 산문을 표의 4번째 행(colspan3)으로 흡수 + rowspan 불일치",
    "backend": "Colab GPU, transformers + mineru_vl_utils.two_step_extract",
    "note": "평탄 인코딩이라 중첩 GT 기준 과소평가. PaddleOCR(0.531)보다 낮은 건 prose-as-row 오류 때문.",
    "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
}
out = HERE / "mineru" / "u1_s6-p011clone.json"
out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✓ mineru/u1_s6-p011clone.json  (TEDS={teds})")
