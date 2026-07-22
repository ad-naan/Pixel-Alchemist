#!/usr/bin/env python3
"""Measure role-specific foreground color profiles in flattened reference text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("--box", nargs=4, type=int, metavar=("X", "Y", "WIDTH", "HEIGHT"), required=True)
    parser.add_argument("--clean", type=Path)
    parser.add_argument("--diff-threshold", type=float, default=18.0)
    parser.add_argument("--bins", type=int, default=10)
    parser.add_argument("--erode", type=int, default=1)
    parser.add_argument("--min-rgb", nargs=3, type=int, default=(0, 0, 0), metavar=("R", "G", "B"))
    parser.add_argument("--max-rgb", nargs=3, type=int, default=(255, 255, 255), metavar=("R", "G", "B"))
    parser.add_argument("--min-luma", type=float, default=0.0)
    parser.add_argument("--max-luma", type=float, default=255.0)
    parser.add_argument("--min-chroma", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def crop_rgb(path: Path, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, width, height = box
    image = Image.open(path).convert("RGB")
    return np.asarray(image.crop((x, y, x + width, y + height)))


def profile(rgb: np.ndarray, mask: np.ndarray, axis: int, bins: int) -> list[dict]:
    length = rgb.shape[axis]
    result: list[dict] = []
    for index in range(bins):
        start = round(index * length / bins)
        end = round((index + 1) * length / bins)
        selector = [slice(None), slice(None)]
        selector[axis] = slice(start, end)
        band_rgb = rgb[tuple(selector)]
        band_mask = mask[tuple(selector)]
        pixels = band_rgb[band_mask]
        item = {"bin": index, "start": start, "end": end, "pixels": int(len(pixels))}
        if len(pixels):
            percentiles = np.percentile(pixels, [25, 50, 75], axis=0)
            item["rgb_p25_p50_p75"] = np.round(percentiles).astype(int).tolist()
        result.append(item)
    return result


def main() -> None:
    args = parse_args()
    box = tuple(args.box)
    rgb = crop_rgb(args.reference, box)
    minimum = np.asarray(args.min_rgb, dtype=np.float32)
    maximum = np.asarray(args.max_rgb, dtype=np.float32)
    mask = np.all((rgb >= minimum) & (rgb <= maximum), axis=2)
    luminance = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    mask &= (luminance >= args.min_luma) & (luminance <= args.max_luma) & (chroma >= args.min_chroma)
    if args.clean:
        clean = crop_rgb(args.clean, box)
        difference = np.max(np.abs(rgb.astype(np.float32) - clean.astype(np.float32)), axis=2)
        mask &= difference >= args.diff_threshold
    if args.erode > 0:
        size = args.erode * 2 + 1
        mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(size))) > 0
    pixels = rgb[mask]
    if not len(pixels):
        raise SystemExit("No foreground pixels matched; tighten the box or relax the filters.")
    payload = {
        "reference": str(args.reference),
        "clean": str(args.clean) if args.clean else None,
        "box_xywh": list(box),
        "mask": {
            "pixels": int(len(pixels)),
            "coverage": float(mask.mean()),
            "erode": args.erode,
            "diff_threshold": args.diff_threshold if args.clean else None,
            "min_rgb": list(args.min_rgb),
            "max_rgb": list(args.max_rgb),
            "min_luma": args.min_luma,
            "max_luma": args.max_luma,
            "min_chroma": args.min_chroma,
        },
        "overall_rgb_p25_p50_p75": np.round(np.percentile(pixels, [25, 50, 75], axis=0)).astype(int).tolist(),
        "x_profile": profile(rgb, mask, axis=1, bins=args.bins),
        "y_profile": profile(rgb, mask, axis=0, bins=args.bins),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
