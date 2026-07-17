from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory project images, fonts, workbooks, vectors, and related assets.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = []
    for path in sorted(item for item in args.root.rglob("*") if item.is_file()):
        row = {"path": str(path), "relative": str(path.relative_to(args.root)), "suffix": path.suffix.lower(), "bytes": path.stat().st_size}
        if path.suffix.lower() in IMAGE_SUFFIXES:
            try:
                with Image.open(path) as image:
                    row.update({
                        "kind": "image",
                        "size": list(image.size),
                        "mode": image.mode,
                        "format": image.format,
                        "frames": int(getattr(image, "n_frames", 1)),
                        "duration_ms": image.info.get("duration"),
                        "loop": image.info.get("loop"),
                    })
            except Exception as error:
                row.update({"kind": "image", "error": str(error)})
        elif path.suffix.lower() in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
            row["kind"] = "font"
        elif path.suffix.lower() in {".xlsx", ".xls", ".csv", ".tsv"}:
            row["kind"] = "spreadsheet"
        elif path.suffix.lower() == ".svg":
            row["kind"] = "vector"
        else:
            row["kind"] = "other"
        rows.append(row)

    payload = {"root": str(args.root.resolve()), "files": rows}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {len(rows)} entries -> {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
