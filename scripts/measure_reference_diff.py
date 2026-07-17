from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def read_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot read image: {path}")
    return image


def components(
    blank: np.ndarray,
    reference: np.ndarray,
    threshold: int,
    minimum_area: int,
    merge_x: int,
    merge_y: int,
) -> list[dict[str, int]]:
    if blank.shape != reference.shape:
        raise ValueError(f"shape mismatch: {blank.shape} != {reference.shape}")
    difference = np.max(cv2.absdiff(blank, reference), axis=2)
    mask = (difference > threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (merge_x, merge_y)))
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3)))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    found = []
    for x, y, width, height, area in stats[1:]:
        if int(area) >= minimum_area:
            found.append({"x": int(x), "y": int(y), "width": int(width), "height": int(height), "area": int(area)})
    return sorted(found, key=lambda item: (item["y"], item["x"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure changed regions between clean backgrounds and finished references.")
    parser.add_argument("blank", type=Path, help="Clean image or directory of clean images.")
    parser.add_argument("reference", type=Path, help="Finished image or directory with matching filenames.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=30)
    parser.add_argument("--minimum-area", type=int, default=60)
    parser.add_argument("--merge-x", type=int, default=31, help="Horizontal closing kernel; increase to merge words into lines.")
    parser.add_argument("--merge-y", type=int, default=7, help="Vertical closing kernel; keep below line spacing.")
    parser.add_argument("--preview-dir", type=Path, help="Optional directory for annotated reference previews.")
    args = parser.parse_args()

    if args.blank.is_file() and args.reference.is_file():
        pairs = [(args.blank, args.reference)]
    elif args.blank.is_dir() and args.reference.is_dir():
        pairs = [
            (blank_path, args.reference / blank_path.name)
            for blank_path in sorted(item for item in args.blank.iterdir() if item.is_file())
            if (args.reference / blank_path.name).exists()
        ]
    else:
        raise ValueError("blank and reference must both be files or both be directories")

    report = {}
    for blank_path, reference_path in pairs:
        blank = read_image(blank_path)
        reference = read_image(reference_path)
        found = components(blank, reference, args.threshold, args.minimum_area, args.merge_x, args.merge_y)
        report_key = reference_path.name if args.blank.is_file() else blank_path.name
        report[report_key] = {
            "canvas": [int(blank.shape[1]), int(blank.shape[0])],
            "components": found,
        }
        if args.preview_dir:
            preview = reference.copy()
            for item in found:
                cv2.rectangle(
                    preview,
                    (item["x"], item["y"]),
                    (item["x"] + item["width"], item["y"] + item["height"]),
                    (0, 0, 255),
                    2,
                )
            args.preview_dir.mkdir(parents=True, exist_ok=True)
            extension = blank_path.suffix if blank_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
            success, encoded = cv2.imencode(extension, preview)
            if success:
                encoded.tofile(args.preview_dir / report_key)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"measured {len(report)} matched files -> {args.output}")


if __name__ == "__main__":
    main()
