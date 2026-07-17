from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont


PALETTE = ["#40E0D0", "#FFB347", "#FF6B8A", "#8FA8FF", "#B7E36B", "#D58BFF", "#66C7FF"]


def variant_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("language") or "default")


def merged_spec(template_name: str, role: str, spec: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    overrides = variant.get("layout_overrides", {}).get(template_name, {})
    return {**spec, **overrides.get(role, {})}


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw configured safe boxes, labels, and coordinates over a template image.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--variant", default="default")
    parser.add_argument("--image", type=Path, help="Optional image override, such as a clean rendered layout.")
    parser.add_argument("--roles", nargs="*", help="Only visualize these element roles.")
    parser.add_argument("--types", nargs="*", default=["text", "icon_text", "button", "image", "erase"])
    parser.add_argument("--fill-alpha", type=int, default=38)
    parser.add_argument("--line-width", type=int, default=3)
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    template = payload["templates"][args.template]
    variants = payload.get("variants") or payload.get("locales") or [{"id": "default"}]
    variant = next((item for item in variants if variant_id(item) == args.variant), None)
    if variant is None:
        raise ValueError(f"unknown variant: {args.variant}")

    if args.image:
        image_path = args.image
    else:
        background_name = variant.get("backgrounds", {}).get(args.template) or variant.get("background") or template["background"]
        image_path = args.background_dir / str(background_name)
    with Image.open(image_path) as source:
        canvas = source.convert("RGBA")
    if canvas.size != tuple(template["canvas"]):
        raise ValueError(f"{canvas.size} != {tuple(template['canvas'])}")

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    label_font = ImageFont.load_default(size=max(12, round(min(canvas.size) / 45)))
    selected_roles = set(args.roles) if args.roles else None
    selected_types = set(args.types)
    report = []
    for index, (role, raw_spec) in enumerate(template.get("elements", {}).items()):
        spec = merged_spec(args.template, role, raw_spec, variant)
        kind = str(spec.get("type", ""))
        if not spec.get("enabled", True) or "box" not in spec or kind not in selected_types:
            continue
        if selected_roles is not None and role not in selected_roles:
            continue
        x, y, width, height = (int(value) for value in spec["box"])
        color = ImageColor.getcolor(PALETTE[index % len(PALETTE)], "RGBA")
        fill = (color[0], color[1], color[2], max(0, min(255, args.fill_alpha)))
        outline = (color[0], color[1], color[2], 255)
        draw.rectangle((x, y, x + width, y + height), fill=fill, outline=outline, width=args.line_width)
        label = f"{role}  [{x}, {y}, {width}, {height}]"
        label_box = draw.textbbox((0, 0), label, font=label_font)
        label_width = label_box[2] - label_box[0] + 12
        label_height = label_box[3] - label_box[1] + 8
        label_y = y - label_height if y >= label_height else y
        draw.rounded_rectangle((x, label_y, min(canvas.width, x + label_width), label_y + label_height), radius=5, fill=(5, 14, 28, 225))
        draw.text((x + 6, label_y + 4 - label_box[1]), label, font=label_font, fill=outline)
        report.append({"role": role, "type": kind, "box": [x, y, width, height]})

    canvas.alpha_composite(overlay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, format="PNG", optimize=True)
    report_path = args.output.with_suffix(".json")
    report_path.write_text(
        json.dumps({"template": args.template, "variant": args.variant, "image": str(image_path), "safe_boxes": report}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"visualized {len(report)} safe boxes -> {args.output}")


if __name__ == "__main__":
    main()
