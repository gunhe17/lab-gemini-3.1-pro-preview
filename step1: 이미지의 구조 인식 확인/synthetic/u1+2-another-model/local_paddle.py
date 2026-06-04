#!/usr/bin/env python3
"""로컬(M1 CPU)에서 PaddleOCR-VL을 s6에 돌려 표 HTML 추출 + 우리 TEDS-Struct 채점.
실행: ../../../.venv-ocr/bin/python local_paddle.py
"""
import glob
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize
from teds import teds_struct_html

from paddleocr import PaddleOCRVL

img = str(SYN / "png" / "s6-p011clone.png")
print("predict 시작(첫 실행은 모델 다운로드 포함)…", flush=True)
pipe = PaddleOCRVL()
res = pipe.predict(img)

outdir = HERE / "paddle_local_out"
raw = ""
for r in res:
    try:
        r.save_to_markdown(save_path=str(outdir))
    except Exception as e:
        print("save_to_markdown 경고:", e, flush=True)
    # 객체에서 직접 markdown 얻기 시도
    for attr in ("markdown", "md"):
        v = getattr(r, attr, None)
        if isinstance(v, str) and "<table" in v:
            raw = v
    if isinstance(getattr(r, "markdown", None), dict):
        t = r.markdown.get("markdown_texts") or r.markdown.get("text")
        if isinstance(t, str):
            raw = t
if "<table" not in raw:
    for f in sorted(glob.glob(str(outdir) + "/**/*.md", recursive=True)) + sorted(glob.glob(str(outdir) + "*.md")):
        raw = open(f, encoding="utf-8").read()
        break

print("=== RAW HEAD (600자) ===", flush=True)
print(raw[:600], flush=True)
(HERE / "paddle_local_raw.md").write_text(raw, encoding="utf-8")

gt = (SYN / "gt" / "s6-p011clone.skeleton.html").read_text(encoding="utf-8")
m = re.search(r"<table.*</table>", raw, re.S | re.I)
if m:
    (HERE / "paddle_local_s6.html").write_text(m.group(0), encoding="utf-8")
    skel = skeletonize(m.group(0))
    print("\n>>> PaddleOCR-VL (로컬)  s6 TEDS-Struct =", round(teds_struct_html(skel, gt), 3), flush=True)
else:
    print("\n⚠ <table> 미발견 — paddle_local_raw.md 확인", flush=True)
