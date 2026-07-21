from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

try:
    import cv2
except ImportError:
    cv2 = None


def resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def safe_output(root: Path, value: str, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must stay inside the output directory")
    resolved_root = root.resolve()
    output = (resolved_root / relative).resolve()
    if output != resolved_root and resolved_root not in output.parents:
        raise ValueError(f"{label} must stay inside the output directory")
    return output


def variant_directory(root: Path, identifier: str) -> Path:
    value = Path(identifier)
    if value.is_absolute() or len(value.parts) != 1 or identifier in {"", ".", ".."}:
        raise ValueError(f"invalid variant id: {identifier!r}")
    return safe_output(root, identifier, "variant id")


def canvas_size(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be [width, height]")
    width, height = (int(item) for item in value)
    if width <= 0 or height <= 0:
        raise ValueError(f"{label} must contain positive dimensions")
    return width, height


def full_quad(size: tuple[int, int]) -> list[list[float]]:
    width, height = size
    return [[0.0, 0.0], [float(width), 0.0], [float(width), float(height)], [0.0, float(height)]]


def quad(value: Any, fallback: list[list[float]], label: str) -> np.ndarray:
    points = fallback if value is None else value
    if not isinstance(points, list) or len(points) != 4 or any(not isinstance(point, list) or len(point) != 2 for point in points):
        raise ValueError(f"{label} must contain four [x, y] points")
    return np.asarray(points, dtype=np.float32)


def transform_matrix(spec: dict[str, Any], source_size: tuple[int, int], target_size: tuple[int, int], label: str) -> np.ndarray:
    if cv2 is None:
        raise RuntimeError("build_layer_family.py requires opencv-python; install requirements.txt in the project environment")
    raw_matrix = spec.get("matrix")
    if raw_matrix is not None:
        matrix = np.asarray(raw_matrix, dtype=np.float64)
        if matrix.size != 9:
            raise ValueError(f"{label}.matrix must contain nine values")
        return matrix.reshape((3, 3))
    has_quad = spec.get("source_quad") is not None or spec.get("destination_quad") is not None
    if not has_quad and source_size != target_size:
        raise ValueError(f"{label} changes canvas size and therefore requires a matrix or an explicit quad mapping")
    source = quad(spec.get("source_quad"), full_quad(source_size), f"{label}.source_quad")
    destination = quad(spec.get("destination_quad"), full_quad(target_size), f"{label}.destination_quad")
    return cv2.getPerspectiveTransform(source, destination).astype(np.float64)


def load_premultiplied(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    rgba[:, :, :3] *= rgba[:, :, 3:4]
    return rgba


def polygon_mask(size: tuple[int, int], polygons: list[Any], scale: int) -> np.ndarray:
    width, height = size
    mask = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(mask)
    for raw_polygon in polygons:
        if not isinstance(raw_polygon, list) or len(raw_polygon) < 3:
            raise ValueError("mask polygons must contain at least three [x, y] points")
        points = [(round(float(point[0]) * scale), round(float(point[1]) * scale)) for point in raw_polygon]
        draw.polygon(points, fill=255)
    return np.asarray(mask, dtype=np.float32) / 255.0


def file_mask(path: Path, size: tuple[int, int], scale: int) -> np.ndarray:
    with Image.open(path) as image:
        mask = image.convert("L")
    expected = (size[0] * scale, size[1] * scale)
    if mask.size != expected:
        mask = mask.resize(expected, Image.Resampling.LANCZOS)
    return np.asarray(mask, dtype=np.float32) / 255.0


def apply_masks(layer: np.ndarray, spec: dict[str, Any], size: tuple[int, int], scale: int, base_dir: Path) -> np.ndarray:
    keep = np.ones(layer.shape[:2], dtype=np.float32)
    clip_mask = spec.get("clip_mask")
    if clip_mask:
        keep *= file_mask(resolve_path(str(clip_mask), base_dir), size, scale)
    clip_polygon = spec.get("clip_polygon")
    if clip_polygon:
        keep *= polygon_mask(size, [clip_polygon], scale)

    occlusion = np.zeros(layer.shape[:2], dtype=np.float32)
    for value in spec.get("occlusion_masks", []):
        occlusion = np.maximum(occlusion, file_mask(resolve_path(str(value), base_dir), size, scale))
    polygons = spec.get("occlusion_polygons", [])
    if polygons:
        occlusion = np.maximum(occlusion, polygon_mask(size, polygons, scale))
    keep *= 1.0 - np.clip(occlusion, 0.0, 1.0)

    result = layer.copy()
    result[:, :, :3] *= keep[:, :, None]
    result[:, :, 3] *= keep
    return result


def warp_layer(
    source: np.ndarray,
    matrix: np.ndarray,
    target_size: tuple[int, int],
    spec: dict[str, Any],
    base_dir: Path,
    supersample: int,
) -> np.ndarray:
    if cv2 is None:
        raise RuntimeError("build_layer_family.py requires opencv-python; install requirements.txt in the project environment")
    width, height = target_size
    scale_matrix = np.asarray([[supersample, 0, 0], [0, supersample, 0], [0, 0, 1]], dtype=np.float64)
    high_resolution_matrix = scale_matrix @ matrix
    warped = cv2.warpPerspective(
        source,
        high_resolution_matrix,
        (width * supersample, height * supersample),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    warped = apply_masks(warped, spec, target_size, supersample, base_dir)
    if supersample > 1:
        warped = cv2.resize(warped, (width, height), interpolation=cv2.INTER_AREA)
    return np.clip(warped, 0.0, 1.0)


def straight_rgba(layer: np.ndarray) -> np.ndarray:
    alpha = layer[:, :, 3:4]
    rgb = np.zeros_like(layer[:, :, :3])
    np.divide(layer[:, :, :3], alpha, out=rgb, where=alpha > 1e-6)
    rgba = np.concatenate((rgb, alpha), axis=2)
    return np.rint(np.clip(rgba, 0.0, 1.0) * 255.0).astype(np.uint8)


def save_layer(layer: np.ndarray, output: Path) -> dict[str, Any]:
    if output.suffix.lower() != ".png":
        raise ValueError(f"transparent layer output must use .png: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rgba = straight_rgba(layer)
    Image.fromarray(rgba, "RGBA").save(output, optimize=True)
    alpha = rgba[:, :, 3]
    points = np.argwhere(alpha > 0)
    alpha_box = None
    if points.size:
        top, left = points.min(axis=0)
        bottom, right = points.max(axis=0)
        alpha_box = [int(left), int(top), int(right - left + 1), int(bottom - top + 1)]
    return {
        "output": str(output),
        "size": [int(rgba.shape[1]), int(rgba.shape[0])],
        "alpha_box": alpha_box,
        "nonzero_alpha_pixels": int(np.count_nonzero(alpha)),
    }


def merged_stage(base: dict[str, Any], override: Any) -> dict[str, Any]:
    return {**base, **override} if isinstance(override, dict) else dict(base)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one supersampled premultiplied-alpha master layer and map it into a family of target canvases.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--variants", nargs="*", help="Only build the selected variant ids.")
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    base_dir = args.config.resolve().parent
    supersample = int(payload.get("supersample", 3))
    if supersample < 1 or supersample > 8:
        raise ValueError("supersample must be between 1 and 8")
    master_base = payload.get("master")
    if not isinstance(master_base, dict):
        raise ValueError("config must define a master object")
    targets = payload.get("targets", {})
    if not isinstance(targets, dict):
        raise ValueError("targets must be an object")
    variants = payload.get("variants", [])
    if not isinstance(variants, list) or not variants:
        raise ValueError("config must define at least one variant")
    requested = set(args.variants or [])
    report: list[dict[str, Any]] = []

    for variant in variants:
        identifier = str(variant.get("id") or "")
        if not identifier:
            raise ValueError("every variant must define id")
        if requested and identifier not in requested:
            continue
        source_value = variant.get("source")
        if not source_value:
            raise ValueError(f"{identifier}: missing source")
        source_path = resolve_path(str(source_value), base_dir)
        source = load_premultiplied(source_path)
        source_size = (int(source.shape[1]), int(source.shape[0]))
        master = merged_stage(master_base, variant.get("master"))
        master_size = canvas_size(master.get("canvas"), "master.canvas")
        master_matrix = transform_matrix(master, source_size, master_size, "master")
        master_layer = warp_layer(source, master_matrix, master_size, master, base_dir, supersample)
        variant_dir = variant_directory(args.output_dir, identifier)
        master_output = safe_output(variant_dir, str(master.get("output", "master.png")), "master.output")
        row = {
            "variant": identifier,
            "source": str(source_path),
            "supersample": supersample,
            "master": {
                **save_layer(master_layer, master_output),
                "matrix": master_matrix.tolist(),
            },
            "targets": {},
        }
        for target_name, target_base in targets.items():
            if not isinstance(target_base, dict):
                raise ValueError(f"target {target_name!r} must be an object")
            target = merged_stage(target_base, variant.get("targets", {}).get(target_name))
            target_size = canvas_size(target.get("canvas"), f"targets.{target_name}.canvas")
            matrix = transform_matrix(target, master_size, target_size, f"targets.{target_name}")
            mapped = warp_layer(master_layer, matrix, target_size, target, base_dir, supersample)
            output = safe_output(variant_dir, str(target.get("output", f"{target_name}.png")), f"targets.{target_name}.output")
            row["targets"][target_name] = {**save_layer(mapped, output), "matrix": matrix.tolist()}
        report.append(row)
        print(f"[done] {identifier}: master + {len(targets)} targets", flush=True)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "layer-family-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(report)} layer families -> {report_path}")


if __name__ == "__main__":
    main()
