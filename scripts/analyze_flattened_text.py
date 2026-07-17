from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont


def resolve_path(value: str, base_dir: Path, skill_dir: Path) -> Path:
    if value.startswith("@skill/"):
        return skill_dir / value.removeprefix("@skill/")
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def color_mask(rgb: np.ndarray, colors: list[str], tolerance: float) -> np.ndarray:
    if not colors:
        return np.zeros(rgb.shape[:2], dtype=np.uint8)
    pixels = rgb.astype(np.float32)
    selected = np.zeros(rgb.shape[:2], dtype=bool)
    for value in colors:
        target = np.array(ImageColor.getrgb(value), dtype=np.float32)
        selected |= np.linalg.norm(pixels - target, axis=2) <= tolerance
    return selected.astype(np.uint8) * 255


def external_region_mask(path: Path, canvas_size: tuple[int, int], search_box: list[int]) -> np.ndarray:
    with Image.open(path) as source:
        mask = np.array(source.convert("L"))
    x, y, width, height = search_box
    if mask.shape == (canvas_size[1], canvas_size[0]):
        return mask[y : y + height, x : x + width]
    if mask.shape == (height, width):
        return mask
    raise ValueError(f"mask {path} has size {mask.shape[::-1]}, expected {canvas_size} or {(width, height)}")


def auto_contrast_mask(rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    kernel = max(9, (min(gray.shape) // 8) | 1)
    background = cv2.medianBlur(gray, kernel)
    residual = cv2.absdiff(gray, background)
    _, mask = cv2.threshold(residual, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return mask


def remove_small_components(mask: np.ndarray, minimum_area: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    cleaned = np.zeros_like(mask)
    for index in range(1, count):
        if int(stats[index, cv2.CC_STAT_AREA]) >= minimum_area:
            cleaned[labels == index] = 255
    return cleaned


def mask_bbox(mask: np.ndarray) -> list[int] | None:
    points = cv2.findNonZero((mask > 0).astype(np.uint8))
    if points is None:
        return None
    x, y, width, height = cv2.boundingRect(points)
    return [int(x), int(y), int(width), int(height)]


def split_line_boxes(mask: np.ndarray, maximum_gap: int = 4) -> list[list[int]]:
    active = np.any(mask > 0, axis=1)
    groups: list[tuple[int, int]] = []
    start: int | None = None
    gap = 0
    for index, value in enumerate(active):
        if value:
            if start is None:
                start = index
            gap = 0
        elif start is not None:
            gap += 1
            if gap > maximum_gap:
                groups.append((start, index - gap + 1))
                start = None
                gap = 0
    if start is not None:
        groups.append((start, len(active)))
    boxes = []
    for top, bottom in groups:
        cropped = mask[top:bottom]
        box = mask_bbox(cropped)
        if box:
            boxes.append([box[0], top + box[1], box[2], box[3]])
    return boxes


def split_expected_lines(mask: np.ndarray, line_count: int, maximum_gap: int) -> list[list[int]]:
    if line_count <= 1:
        return split_line_boxes(mask, maximum_gap)
    ys = np.where(mask > 0)[0].astype(np.float32)
    if len(ys) < line_count:
        return split_line_boxes(mask, maximum_gap)
    _, labels, centers = cv2.kmeans(
        ys.reshape(-1, 1),
        line_count,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.1),
        10,
        cv2.KMEANS_PP_CENTERS,
    )
    ordered = np.argsort(centers[:, 0])
    boxes = []
    foreground_y, foreground_x = np.where(mask > 0)
    for cluster in ordered:
        selected = labels[:, 0] == cluster
        cluster_y = foreground_y[selected]
        cluster_x = foreground_x[selected]
        if len(cluster_x):
            boxes.append(
                [
                    int(cluster_x.min()),
                    int(cluster_y.min()),
                    int(cluster_x.max() - cluster_x.min() + 1),
                    int(cluster_y.max() - cluster_y.min() + 1),
                ]
            )
    return boxes


def render_tight_mask(text: str, font_path: Path, size: int) -> np.ndarray:
    font = ImageFont.truetype(str(font_path), size, layout_engine=ImageFont.Layout.RAQM)
    probe = Image.new("L", (8, 8), 0)
    draw = ImageDraw.Draw(probe)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    width = max(1, right - left)
    height = max(1, bottom - top)
    image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(image).text((-left, -top), text, font=font, fill=255)
    return np.array(image)


def shape_iou(observed: np.ndarray, rendered: np.ndarray) -> float:
    if not observed.any() or not rendered.any():
        return 0.0
    resized = cv2.resize(rendered, (observed.shape[1], observed.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    actual = observed > 0
    union = np.logical_or(actual, resized).sum()
    return float(np.logical_and(actual, resized).sum() / union) if union else 0.0


def candidate_metadata(item: str | dict[str, Any], base_dir: Path, skill_dir: Path) -> dict[str, Any]:
    if isinstance(item, str):
        path = resolve_path(item, base_dir, skill_dir)
        family = path.stem
        weight = "bold" if any(token in path.stem.lower() for token in ("bold", "black", "heavy", "semibold")) else "regular"
        return {"path": path, "source": item, "family": family, "weight": weight}
    source = str(item["path"])
    path = resolve_path(source, base_dir, skill_dir)
    return {"path": path, "source": source, "family": item.get("family", path.stem), "weight": item.get("weight", "regular")}


def match_font(
    line_masks: list[np.ndarray],
    lines: list[str],
    candidates: list[dict[str, Any]],
    minimum_size: int,
    maximum_size: int,
) -> list[dict[str, Any]]:
    matches = []
    for candidate in candidates:
        if not candidate["path"].exists():
            continue
        for size in range(minimum_size, maximum_size + 1):
            dimension_error = 0.0
            ious = []
            valid = True
            for observed, text in zip(line_masks, lines, strict=True):
                try:
                    rendered = render_tight_mask(text, candidate["path"], size)
                except OSError:
                    valid = False
                    break
                dimension_error += abs(math.log(rendered.shape[1] / observed.shape[1]))
                dimension_error += abs(math.log(rendered.shape[0] / observed.shape[0]))
                ious.append(shape_iou(observed, rendered))
            if valid:
                score = dimension_error / len(lines) + (1.0 - sum(ious) / len(ious))
                matches.append(
                    {
                        "family": candidate["family"],
                        "weight": candidate["weight"],
                        "path": candidate["source"],
                        "font_size": size,
                        "score": round(float(score), 6),
                        "shape_iou": round(float(sum(ious) / len(ious)), 6),
                    }
                )
    return sorted(matches, key=lambda item: item["score"])[:5]


def infer_alignment(search_box: list[int], ink_box: list[int]) -> str:
    sx, _, sw, _ = search_box
    ix, _, iw, _ = ink_box
    left = ix - sx
    right = sx + sw - (ix + iw)
    if abs(left - right) <= max(4, sw * 0.06):
        return "center"
    return "left" if left < right else "right"


def median_color(rgb: np.ndarray, mask: np.ndarray) -> str | None:
    pixels = rgb[mask > 0]
    if not len(pixels):
        return None
    color = np.median(pixels, axis=0).astype(int)
    return "#{:02X}{:02X}{:02X}".format(*color)


def shifted_box(box: list[int], offset_x: int, offset_y: int) -> list[int]:
    return [box[0] + offset_x, box[1] + offset_y, box[2], box[3]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover precise text masks, coordinates, and typography estimates from a flattened image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("spec", type=Path, help="JSON containing regions, known copy, colors, and font candidates.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    base_dir = args.spec.resolve().parent
    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    with Image.open(args.image) as source:
        pil_image = source.convert("RGB")
    rgb = np.array(pil_image)
    height, width = rgb.shape[:2]
    combined_ink = np.zeros((height, width), dtype=np.uint8)
    combined_erase = np.zeros((height, width), dtype=np.uint8)
    preview = rgb.copy()
    report_regions = []

    default_candidates = [candidate_metadata(item, base_dir, skill_dir) for item in payload.get("font_candidates", [])]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for index, region in enumerate(payload["regions"]):
        role = str(region.get("id", f"text-{index + 1}"))
        search_box = [int(value) for value in region["search_box"]]
        x, y, box_width, box_height = search_box
        if x < 0 or y < 0 or x + box_width > width or y + box_height > height:
            raise ValueError(f"{role}: search_box exceeds canvas")
        roi = rgb[y : y + box_height, x : x + box_width]
        tolerance = float(region.get("color_tolerance", payload.get("color_tolerance", 64)))
        fill_colors = list(region.get("fill_colors", []))
        stroke_colors = list(region.get("stroke_colors", []))
        shadow_colors = list(region.get("shadow_colors", []))
        fill_mask_value = region.get("fill_mask_path") or region.get("mask_path")
        stroke_mask_value = region.get("stroke_mask_path")
        shadow_mask_value = region.get("shadow_mask_path")
        fill_mask = (
            external_region_mask(resolve_path(str(fill_mask_value), base_dir, skill_dir), (width, height), search_box)
            if fill_mask_value
            else color_mask(roi, fill_colors, tolerance) if fill_colors else auto_contrast_mask(roi)
        )
        stroke_mask = (
            external_region_mask(resolve_path(str(stroke_mask_value), base_dir, skill_dir), (width, height), search_box)
            if stroke_mask_value
            else color_mask(roi, stroke_colors, tolerance)
        )
        shadow_mask = (
            external_region_mask(resolve_path(str(shadow_mask_value), base_dir, skill_dir), (width, height), search_box)
            if shadow_mask_value
            else color_mask(roi, shadow_colors, tolerance)
        )
        minimum_area = int(region.get("minimum_component_area", 4))
        fill_mask = remove_small_components(fill_mask, minimum_area)
        stroke_mask = remove_small_components(stroke_mask, minimum_area)
        shadow_mask = remove_small_components(shadow_mask, minimum_area)
        ink_mask = np.maximum(fill_mask, stroke_mask)
        effect_mask = np.maximum(ink_mask, shadow_mask)
        local_box = mask_bbox(effect_mask)
        if local_box is None:
            raise ValueError(f"{role}: no text pixels detected; provide fill_colors or a tighter search_box")
        exact_box = shifted_box(local_box, x, y)
        padding = region.get("safe_padding", payload.get("safe_padding", [4, 4, 4, 4]))
        if isinstance(padding, (int, float)):
            padding = [padding] * 4
        left, top, right, bottom = (int(value) for value in padding)
        safe_x = max(0, exact_box[0] - left)
        safe_y = max(0, exact_box[1] - top)
        safe_right = min(width, exact_box[0] + exact_box[2] + right)
        safe_bottom = min(height, exact_box[1] + exact_box[3] + bottom)
        safe_box = [safe_x, safe_y, safe_right - safe_x, safe_bottom - safe_y]

        lines = list(region.get("lines") or str(region.get("text", "")).splitlines())
        if lines == [""]:
            lines = []
        line_boxes_local = split_expected_lines(fill_mask, len(lines), int(region.get("maximum_line_gap", 5)))
        line_boxes = [shifted_box(box, x, y) for box in line_boxes_local]
        matches: list[dict[str, Any]] = []
        candidates = [candidate_metadata(item, base_dir, skill_dir) for item in region.get("font_candidates", [])] or default_candidates
        if lines and candidates and len(lines) == len(line_boxes_local):
            line_masks = []
            for line_box in line_boxes_local:
                lx, ly, lw, lh = line_box
                line_masks.append(fill_mask[ly : ly + lh, lx : lx + lw])
            matches = match_font(
                line_masks,
                lines,
                candidates,
                int(region.get("min_font_size", 6)),
                int(region.get("max_font_size", max(12, box_height * 2))),
            )

        erase_expand = int(region.get("erase_expand", payload.get("erase_expand", 2)))
        erase_mask = effect_mask
        if erase_expand > 0:
            erase_mask = cv2.dilate(erase_mask, np.ones((erase_expand * 2 + 1, erase_expand * 2 + 1), np.uint8))
        region_ink_full = np.zeros_like(combined_ink)
        region_erase_full = np.zeros_like(combined_erase)
        region_ink_full[y : y + box_height, x : x + box_width] = effect_mask
        region_erase_full[y : y + box_height, x : x + box_width] = erase_mask
        combined_ink = np.maximum(combined_ink, region_ink_full)
        combined_erase = np.maximum(combined_erase, region_erase_full)
        Image.fromarray(region_ink_full).save(args.output_dir / f"{role}-ink-mask.png")
        Image.fromarray(region_erase_full).save(args.output_dir / f"{role}-erase-mask.png")

        best = matches[0] if matches else None
        line_height = None
        if len(line_boxes) > 1 and best:
            starts = [box[1] for box in line_boxes]
            line_height = round(float(np.median(np.diff(starts)) / best["font_size"]), 4)
        stroke_width = 0.0
        if stroke_mask.any() and fill_mask.any():
            distance = cv2.distanceTransform((fill_mask == 0).astype(np.uint8), cv2.DIST_L2, 5)
            values = distance[stroke_mask > 0]
            stroke_width = round(float(np.percentile(values, 90)), 3) if len(values) else 0.0

        render_spec: dict[str, Any] = {
            "type": "text",
            "fixed_text": str(region.get("text", "")),
            "box": safe_box,
            "max_lines": max(1, len(lines) or len(line_boxes)),
            "align": infer_alignment(search_box, exact_box),
            "color": median_color(roi, fill_mask),
        }
        if best:
            render_spec.update(
                {
                    "font_path": best["path"],
                    "weight": best["weight"],
                    "max_font_size": best["font_size"],
                    "min_font_size": best["font_size"],
                }
            )
        if line_height:
            render_spec["line_height"] = line_height
        if stroke_width > 0:
            render_spec.update({"stroke_width": max(1, round(stroke_width)), "stroke_color": median_color(roi, stroke_mask)})

        report_regions.append(
            {
                "id": role,
                "search_box": search_box,
                "ink_box": exact_box,
                "safe_box": safe_box,
                "line_boxes": line_boxes,
                "fill_color": median_color(roi, fill_mask),
                "stroke_color": median_color(roi, stroke_mask),
                "shadow_color": median_color(roi, shadow_mask),
                "stroke_width_estimate": stroke_width,
                "font_matches": matches,
                "render_spec": render_spec,
            }
        )
        cv2.rectangle(preview, (exact_box[0], exact_box[1]), (exact_box[0] + exact_box[2], exact_box[1] + exact_box[3]), (255, 65, 65), 2)
        cv2.rectangle(preview, (safe_box[0], safe_box[1]), (safe_box[0] + safe_box[2], safe_box[1] + safe_box[3]), (50, 225, 210), 2)
        label = f"{role}: {exact_box}"
        cv2.putText(preview, label, (safe_box[0], max(18, safe_box[1] - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 225, 210), 1, cv2.LINE_AA)

    Image.fromarray(combined_ink).save(args.output_dir / "combined-ink-mask.png")
    Image.fromarray(combined_erase).save(args.output_dir / "combined-erase-mask.png")
    Image.fromarray(preview).save(args.output_dir / "measurement-preview.png")
    report = {"image": str(args.image), "canvas": [width, height], "regions": report_regions}
    (args.output_dir / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"analyzed {len(report_regions)} text regions -> {args.output_dir}")


if __name__ == "__main__":
    main()
