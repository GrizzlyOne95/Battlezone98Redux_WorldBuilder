from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a multi-resolution Windows ICO from a 512px PNG")
    parser.add_argument("source_png", type=Path)
    parser.add_argument("output_ico", type=Path)
    args = parser.parse_args()

    with Image.open(args.source_png) as image:
        rgba = image.convert("RGBA")
        rgba.save(
            args.output_ico,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
