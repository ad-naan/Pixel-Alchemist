from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageSequence


def variant_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("language") or "default")


def representative_frames(path: Path) -> list[Image.Image]:
    with Image.open(path) as source:
        count = int(getattr(source, "n_frames", 1))
        indices = sorted({0, count // 2, count - 1}) if count > 1 else [0]
        frames = []
        for index in indices:
            source.seek(index)
            frames.append(source.convert("RGB").copy())
        return frames


def fit_inside(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    result = image.copy()
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def metric_summary(row: dict[str, Any] | None) -> str:
    if not row or not isinstance(row.get("metrics"), dict):
        return "metrics: missing"
    values = []
    for role, metrics in row["metrics"].items():
        if not isinstance(metrics, dict) or metrics.get("font_size") is None:
            continue
        line_count = metrics.get("line_count")
        if line_count is None and isinstance(metrics.get("lines"), list):
            line_count = len(metrics["lines"])
        value = f"{role} {metrics['font_size']}px"
        if line_count is not None:
            value += f"/{line_count}L"
        values.append(value)
    if not values:
        return "metrics: no text"
    summary = " | ".join(values)
    return summary if len(summary) <= 90 else summary[:87] + "..."


def load_violations(path: Path | None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in payload.get("violations", []):
        key = (str(item.get("variant")), str(item.get("template")))
        result.setdefault(key, []).append(item)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-template QA contact sheets for every rendered variant.")
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Render report; defaults to OUTPUT_DIR/render-report.json.")
    parser.add_argument("--validation-report", type=Path, help="Optional JSON written by validate_outputs.py --json-output.")
    parser.add_argument("--variants", nargs="*")
    parser.add_argument("--templates", nargs="*")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cell-width", type=int, default=420)
    parser.add_argument("--cell-height", type=int, default=320)
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    variants = payload.get("variants") or payload.get("locales") or [{"id": "default", "language": "default"}]
    selected_variants = set(args.variants or [variant_id(item) for item in variants])
    selected_templates = set(args.templates or payload.get("templates", {}).keys())
    report_path = args.report or args.output_dir / "render-report.json"
    report_rows = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else []
    report_index = {(str(row.get("variant")), str(row.get("template"))): row for row in report_rows}
    violations = load_violations(args.validation_report)
    label_font = ImageFont.load_default(size=16)
    small_font = ImageFont.load_default(size=13)
    args.qa_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for template_name, template in payload.get("templates", {}).items():
        if template_name not in selected_templates:
            continue
        entries = []
        for variant in variants:
            identifier = variant_id(variant)
            if identifier not in selected_variants and str(variant.get("language", "default")) not in selected_variants:
                continue
            path = args.output_dir / identifier / str(template["output"])
            if path.exists():
                entries.append((variant, path))
        if not entries:
            continue
        columns = max(1, min(args.columns, len(entries)))
        rows = math.ceil(len(entries) / columns)
        sheet = Image.new("RGB", (columns * args.cell_width, rows * args.cell_height), "#E9EEF5")
        image_height = args.cell_height - 62
        for index, (variant, path) in enumerate(entries):
            identifier = variant_id(variant)
            origin_x = (index % columns) * args.cell_width
            origin_y = (index // columns) * args.cell_height
            cell = Image.new("RGB", (args.cell_width - 8, args.cell_height - 8), "#FFFFFF")
            frames = representative_frames(path)
            pane_width = max(1, (cell.width - 12 - 4 * (len(frames) - 1)) // len(frames))
            for frame_index, frame in enumerate(frames):
                preview = fit_inside(frame, (pane_width, image_height - 12))
                pane_x = 6 + frame_index * (pane_width + 4)
                paste_x = pane_x + (pane_width - preview.width) // 2
                paste_y = 6 + (image_height - 12 - preview.height) // 2
                cell.paste(preview, (paste_x, paste_y))
            draw = ImageDraw.Draw(cell)
            current_violations = violations.get((identifier, template_name), [])
            color = "#D62F2F" if current_violations else "#16835B"
            draw.rectangle((0, 0, cell.width - 1, cell.height - 1), outline=color, width=4 if current_violations else 2)
            language = str(variant.get("language", "default"))
            draw.text((8, image_height + 2), f"{identifier}  [{language}]", font=label_font, fill="#101828")
            summary = metric_summary(report_index.get((identifier, template_name)))
            draw.text((8, image_height + 24), summary, font=small_font, fill="#475467")
            if current_violations:
                rules = ", ".join(sorted({str(item.get("rule")) for item in current_violations}))
                draw.text((cell.width - 8, image_height + 2), rules, font=small_font, fill=color, anchor="ra")
            sheet.paste(cell, (origin_x + 4, origin_y + 4))
        output = args.qa_dir / f"{template_name}-qa-grid.png"
        sheet.save(output, format="PNG", optimize=True)
        manifest.append({"template": template_name, "output": str(output), "variants": len(entries), "grid": [columns, rows]})
        print(f"[qa] {template_name}: {len(entries)} variants -> {output}")

    (args.qa_dir / "qa-grid-report.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
