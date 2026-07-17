from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


def polynomial_reconstruction(rgb: np.ndarray, mask: np.ndarray, ring_width: int) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    kernel = np.ones((ring_width * 2 + 1, ring_width * 2 + 1), np.uint8)
    ring = (cv2.dilate(binary, kernel) > 0) & (binary == 0)
    ys, xs = np.where(ring)
    target_y, target_x = np.where(binary > 0)
    if len(xs) < 24:
        return cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    center_x = float(xs.mean())
    center_y = float(ys.mean())
    scale_x = max(1.0, float(np.ptp(xs)) / 2)
    scale_y = max(1.0, float(np.ptp(ys)) / 2)

    def features(x_values: np.ndarray, y_values: np.ndarray) -> np.ndarray:
        nx = (x_values - center_x) / scale_x
        ny = (y_values - center_y) / scale_y
        return np.column_stack((np.ones_like(nx), nx, ny, nx * nx, nx * ny, ny * ny))

    design = features(xs.astype(float), ys.astype(float))
    target_design = features(target_x.astype(float), target_y.astype(float))
    restored = rgb.copy().astype(float)
    for channel in range(3):
        coefficients, *_ = np.linalg.lstsq(design, rgb[ys, xs, channel].astype(float), rcond=None)
        restored[target_y, target_x, channel] = target_design @ coefficients
    return np.clip(restored, 0, 255).astype(np.uint8)


def boundary_score(composite: np.ndarray, mask: np.ndarray) -> float:
    binary = (mask > 0).astype(np.uint8)
    inner = (binary > 0) & (cv2.erode(binary, np.ones((3, 3), np.uint8)) == 0)
    if not inner.any():
        return 0.0
    blurred = cv2.GaussianBlur(composite, (3, 3), 0)
    return float(np.mean(np.abs(composite[inner].astype(float) - blurred[inner].astype(float))))


def reconstruct(rgb: np.ndarray, mask: np.ndarray, method: str, radius: float, ring_width: int) -> tuple[np.ndarray, dict[str, Any]]:
    candidates: dict[str, np.ndarray] = {}
    if method in {"auto", "telea"}:
        candidates["telea"] = cv2.inpaint(rgb, mask, radius, cv2.INPAINT_TELEA)
    if method in {"auto", "ns"}:
        candidates["ns"] = cv2.inpaint(rgb, mask, radius, cv2.INPAINT_NS)
    if method in {"auto", "polynomial"}:
        candidates["polynomial"] = polynomial_reconstruction(rgb, mask, ring_width)
    scores = {}
    binary = mask > 0
    for name, candidate in candidates.items():
        composite = rgb.copy()
        composite[binary] = candidate[binary]
        scores[name] = boundary_score(composite, mask)
    selected = min(scores, key=scores.get)
    return candidates[selected], {"selected_method": selected, "candidate_boundary_scores": {key: round(value, 4) for key, value in scores.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Erase text with a precise mask while keeping every pixel outside the mask byte-identical.")
    parser.add_argument("image", type=Path)
    parser.add_argument("mask", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--method", choices=["auto", "telea", "ns", "polynomial"], default="auto")
    parser.add_argument("--radius", type=float, default=3.0)
    parser.add_argument("--ring-width", type=int, default=10)
    parser.add_argument("--ground-truth", type=Path, help="Optional clean image used only for QA metrics, never for reconstruction.")
    args = parser.parse_args()

    with Image.open(args.image) as source:
        source_rgba = np.array(source.convert("RGBA"))
    with Image.open(args.mask) as source:
        mask = np.array(source.convert("L"))
    if mask.shape != source_rgba.shape[:2]:
        raise ValueError(f"mask size {mask.shape[::-1]} does not match image size {source_rgba.shape[1::-1]}")
    mask = ((mask > 0).astype(np.uint8) * 255)
    if not mask.any():
        raise ValueError("mask is empty")

    rgb = source_rgba[:, :, :3]
    candidate, metrics = reconstruct(rgb, mask, args.method, args.radius, args.ring_width)
    binary = mask > 0
    output_rgba = source_rgba.copy()
    output_rgba[binary, :3] = candidate[binary]
    changed = np.any(output_rgba != source_rgba, axis=2)
    outside_changed = int(np.count_nonzero(changed & ~binary))
    if outside_changed:
        raise AssertionError(f"{outside_changed} pixels outside the erase mask changed")

    points = cv2.findNonZero(binary.astype(np.uint8))
    x, y, width, height = cv2.boundingRect(points)
    report: dict[str, Any] = {
        **metrics,
        "mask_bbox": [int(x), int(y), int(width), int(height)],
        "mask_pixels": int(np.count_nonzero(binary)),
        "changed_inside_pixels": int(np.count_nonzero(changed & binary)),
        "changed_outside_mask_pixels": outside_changed,
        "outside_mask_byte_identical": outside_changed == 0,
    }
    if args.ground_truth:
        with Image.open(args.ground_truth) as source:
            truth = np.array(source.convert("RGBA"))
        if truth.shape != output_rgba.shape:
            raise ValueError("ground-truth size does not match output")
        report["ground_truth_mae_inside_mask"] = round(float(np.mean(np.abs(output_rgba[binary, :3].astype(float) - truth[binary, :3].astype(float)))), 4)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output_rgba, "RGBA").save(args.output)
    report_path = args.report or args.output.with_suffix(".json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
