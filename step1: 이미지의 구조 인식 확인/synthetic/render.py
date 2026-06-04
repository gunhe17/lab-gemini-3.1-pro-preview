#!/usr/bin/env python3.12
"""HTML → PNG 렌더러 (Chrome headless 스크린샷 + PIL 여백 트림).

추가 설치 없이 시스템 Chrome.app으로 렌더 → PIL로 흰 여백을 잘라 표만 남긴다.
2배 스케일로 글자를 또렷하게(인식 천장이 해상도에 막히지 않도록).

사용:
  python3.12 render.py            # html/*.html 전체 → png/<id>.png
  python3.12 render.py s4-nested-asym
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).parent
HTML = HERE / "html"
PNG = HERE / "png"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SCALE = 2
WIN = (1200, 2800)   # 충분히 크게 잡고 트림으로 줄인다
MARGIN = 16          # 트림 후 남길 흰 여백(px, 스케일 적용 전 기준 아님—실픽셀)


def shoot(html_path: Path, out_png: Path) -> None:
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=" + str(SCALE),
        "--default-background-color=FFFFFFFF",
        f"--screenshot={out_png}",
        f"--window-size={WIN[0]},{WIN[1]}",
        html_path.as_uri(),
    ], check=True, capture_output=True)


def trim(png_path: Path) -> tuple[int, int]:
    im = Image.open(png_path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bbox = ImageChops.difference(im, bg).getbbox()
    if bbox:
        l, t, r, b = bbox
        l = max(0, l - MARGIN); t = max(0, t - MARGIN)
        r = min(im.width, r + MARGIN); b = min(im.height, b + MARGIN)
        im = im.crop((l, t, r, b))
    im.save(png_path)
    return im.size


def render_one(html_path: Path) -> None:
    PNG.mkdir(exist_ok=True)
    out = PNG / f"{html_path.stem}.png"
    with tempfile.TemporaryDirectory() as _:
        shoot(html_path, out)
    w, h = trim(out)
    print(f"✓ {out.name}  {w}×{h}px")


def main() -> None:
    if not Path(CHROME).exists():
        sys.exit(f"Chrome 없음: {CHROME}")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = [HTML / f"{args[0]}.html"] if args else sorted(HTML.glob("*.html"))
    for f in files:
        render_one(f)


if __name__ == "__main__":
    main()
