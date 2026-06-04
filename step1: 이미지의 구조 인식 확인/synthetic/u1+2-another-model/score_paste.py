#!/usr/bin/env python3.12
"""호스티드 데모(PaddleOCR-VL / MinerU)가 뱉은 표 출력을 우리 TEDS-Struct로 채점.

데모 출력(HTML 표 또는 마크다운)을 파일/stdin으로 받아, s6 정답 골격과 비교.
부모(synthetic)의 skeletonize·teds를 재사용 — u1/u2와 동일 잣대.

사용:
  python3 score_paste.py <붙여넣은_출력.txt>
  pbpaste | python3 score_paste.py            # 클립보드(macOS)
  python3 score_paste.py - <<'EOF' ... EOF    # heredoc
옵션: 두번째 인자로 정답 페이지(기본 s6-p011clone). 예: python3 score_paste.py out.txt s4-nested-asym
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
SYN = HERE.parent
sys.path.insert(0, str(SYN))
from skeletonize import skeletonize          # noqa: E402
from teds import teds_struct_html            # noqa: E402

GTDIR = SYN / "gt"


def main():
    args = [a for a in sys.argv[1:]]
    page = "s6-p011clone"
    src = None
    for a in args:
        if a in ("-",):
            src = sys.stdin.read()
        elif (GTDIR / f"{a}.skeleton.html").exists():
            page = a
        elif Path(a).exists():
            src = Path(a).read_text(encoding="utf-8")
    if src is None:
        src = sys.stdin.read()

    gt = (GTDIR / f"{page}.skeleton.html").read_text(encoding="utf-8")
    m = re.search(r"<table.*</table>", src, re.S | re.I)
    if not m:
        print("⚠ 입력에 <table>...</table> 없음. 마크다운 파이프표면 알려주세요(변환 추가).")
        print("입력 앞 300자:", src[:300])
        return
    skel = skeletonize(m.group(0))
    score = teds_struct_html(skel, gt)
    print(f"page={page}  TEDS-Struct = {score:.3f}")
    print(f"(기준: Gemini 최고 0.875 · 1.0=완벽)")
    print("--- 골격(normalized) ---")
    print(skel)


if __name__ == "__main__":
    main()
