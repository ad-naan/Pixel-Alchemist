from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def fit(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        source.seek(0)
        image = source.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one overview grouped by variant directories.")
    parser.add_argument("root", type=Path, help="Directory containing one subdirectory per variant.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--variants", nargs="*", help="Optional ordered variant directory names.")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cell-width", type=int, default=420)
    parser.add_argument("--cell-height", type=int, default=320)
    parser.add_argument("--quality", type=int, default=90)
    args = parser.parse_args()

    variants = args.variants or sorted(path.name for path in args.root.iterdir() if path.is_dir())
    groups: list[tuple[str, list[Path]]] = []
    for variant in variants:
        folder = args.root / variant
        files = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in EXTENSIONS)
        if files:
            groups.append((variant, files))
    if not groups:
        raise SystemExit("No variant images found")

    columns = max(1, args.columns)
    label_h = 44
    group_gap = 22
    heights = [label_h + math.ceil(len(files) / columns) * args.cell_height + group_gap for _, files in groups]
    width = columns * args.cell_width
    sheet = Image.new("RGB", (width, sum(heights)), "#151821")
    draw = ImageDraw.Draw(sheet)
    title_font = ImageFont.load_default(size=22)
    label_font = ImageFont.load_default(size=14)
    y = 0
    for (variant, files), group_h in zip(groups, heights):
        draw.text((12, y + 10), f"{variant} · {len(files)} outputs", font=title_font, fill="white")
        for index, path in enumerate(files):
            x = (index % columns) * args.cell_width
            cell_y = y + label_h + (index // columns) * args.cell_height
            draw.rectangle((x + 4, cell_y + 4, x + args.cell_width - 4, cell_y + args.cell_height - 4), fill="#080c16", outline="#4a5160", width=2)
            draw.text((x + 12, cell_y + 10), path.name, font=label_font, fill="#efc28c")
            image = fit(path, (args.cell_width - 24, args.cell_height - 54))
            px = x + (args.cell_width - image.width) // 2
            py = cell_y + 42 + (args.cell_height - 42 - image.height) // 2
            sheet.paste(image, (px, py))
        y += group_h

    args.output.parent.mkdir(parents=True, exist_ok=True)
    suffix = args.output.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        sheet.save(args.output, quality=args.quality, subsampling=0)
    else:
        sheet.save(args.output, optimize=True)
    print(args.output)


if __name__ == "__main__":
    main()
