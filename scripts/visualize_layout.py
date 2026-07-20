from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont

try:
    from .layout import resolve_elements, resolve_obstacles
    from .render_batch import apply_flow_boxes
except ImportError:
    from layout import resolve_elements, resolve_obstacles
    from render_batch import apply_flow_boxes


PALETTE = ["#40E0D0", "#FFB347", "#FF6B8A", "#8FA8FF", "#B7E36B", "#D58BFF", "#66C7FF"]


def variant_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("language") or "default")


def load_report_row(path: Path | None, template: str, variant: str) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))
    return next((row for row in rows if str(row.get("template")) == template and str(row.get("variant")) == variant), None)


def load_violations(path: Path | None, template: str, variant: str) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload.get("violations", []) if str(item.get("template")) == template and str(item.get("variant")) == variant]


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw configured safe boxes, labels, and coordinates over a template image.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--variant", default="default")
    parser.add_argument("--image", type=Path, help="Optional image override, such as a clean rendered layout.")
    parser.add_argument("--report", type=Path, help="Optional render-report.json; overlays actual ink and compound-group bounds.")
    parser.add_argument("--validation-report", type=Path, help="Optional validator JSON; highlights roles involved in failed rules.")
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
    report_row = load_report_row(args.report, args.template, args.variant)
    actual_metrics = report_row.get("metrics", {}) if report_row else {}
    violations = load_violations(args.validation_report, args.template, args.variant)
    failed_roles = {str(role) for item in violations for role in item.get("roles", [])}
    configured_specs = resolve_elements(args.template, template, variant)
    resolved_specs = apply_flow_boxes(
        configured_specs,
        template,
        template_name=args.template,
        variant=variant,
    )
    obstacles = []
    for name, raw in resolve_obstacles(args.template, template, variant).items():
        obstacle_box = raw.get("box") if isinstance(raw, dict) else raw
        if not (isinstance(obstacle_box, list) and len(obstacle_box) == 4):
            continue
        ox, oy, ow, oh = (int(round(value)) for value in obstacle_box)
        padding = int(round(raw.get("padding", 0))) if isinstance(raw, dict) else 0
        draw.rectangle(
            (ox - padding, oy - padding, ox + ow + padding, oy + oh + padding),
            fill=(255, 48, 48, 32),
            outline=(255, 48, 48, 255),
            width=max(2, args.line_width),
        )
        draw.text((ox + 5, oy + 5), f"obstacle:{name}", font=label_font, fill=(255, 220, 220, 255))
        obstacles.append({"name": str(name), "box": [ox, oy, ow, oh], "padding": padding})
    safe_boxes = []
    for index, (role, spec) in enumerate(resolved_specs.items()):
        kind = str(spec.get("type", ""))
        if not spec.get("enabled", True) or "box" not in spec or kind not in selected_types:
            continue
        if selected_roles is not None and role not in selected_roles:
            continue
        x, y, width, height = (int(value) for value in spec["box"])
        color = ImageColor.getcolor(PALETTE[index % len(PALETTE)], "RGBA")
        configured = configured_specs.get(role, {})
        flow_box = configured.get("flow_box")
        if isinstance(flow_box, list) and len(flow_box) == 4:
            fx, fy, fw, fh = (int(round(value)) for value in flow_box)
            draw.rectangle(
                (fx, fy, fx + fw, fy + fh),
                outline=(45, 225, 255, 220),
                width=max(1, args.line_width - 1),
            )
        fill = (color[0], color[1], color[2], max(0, min(255, args.fill_alpha)))
        outline = (220, 35, 35, 255) if role in failed_roles else (color[0], color[1], color[2], 255)
        draw.rectangle((x, y, x + width, y + height), fill=fill, outline=outline, width=args.line_width)
        label = f"{role}  [{x}, {y}, {width}, {height}]"
        label_box = draw.textbbox((0, 0), label, font=label_font)
        label_width = label_box[2] - label_box[0] + 12
        label_height = label_box[3] - label_box[1] + 8
        label_y = y - label_height if y >= label_height else y
        draw.rounded_rectangle((x, label_y, min(canvas.width, x + label_width), label_y + label_height), radius=5, fill=(5, 14, 28, 225))
        draw.text((x + 6, label_y + 4 - label_box[1]), label, font=label_font, fill=outline)
        item = {"role": role, "type": kind, "box": [x, y, width, height]}
        if isinstance(flow_box, list) and len(flow_box) == 4:
            item["flow_box"] = list(flow_box)
            item["configured_box"] = list(configured.get("box", []))
        metrics = actual_metrics.get(role, {}) if isinstance(actual_metrics, dict) else {}
        for metric_name, metric_color in (("ink_box", (255, 255, 255, 255)), ("group_box", (255, 72, 72, 255))):
            metric_box = metrics.get(metric_name) if isinstance(metrics, dict) else None
            if isinstance(metric_box, list) and len(metric_box) == 4:
                mx, my, mw, mh = (int(round(value)) for value in metric_box)
                draw.rectangle((mx, my, mx + mw, my + mh), outline=metric_color, width=max(1, args.line_width - 1))
                item[metric_name] = [mx, my, mw, mh]
        safe_boxes.append(item)

    guides = []
    for name, group in template.get("alignment_groups", {}).items():
        override = variant.get("alignment_overrides", {}).get(args.template, {}).get(name, {})
        group = {**group, **override}
        edge = str(group.get("edge", "left"))
        anchor_role = group.get("anchor_role")
        if group.get("position") is not None:
            position = float(group["position"])
        elif anchor_role in resolved_specs and "box" in resolved_specs[anchor_role]:
            ax, ay, aw, ah = (float(value) for value in resolved_specs[anchor_role]["box"])
            position = {"left": ax, "right": ax + aw, "center": ax + aw / 2}[edge]
        else:
            continue
        if edge in {"left", "right", "center"}:
            px = int(round(position))
            draw.line((px, 0, px, canvas.height), fill=(255, 222, 61, 190), width=1)
            guides.append({"name": name, "edge": edge, "position": position})

    canvas.alpha_composite(overlay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, format="PNG", optimize=True)
    report_path = args.output.with_suffix(".json")
    report_path.write_text(
        json.dumps({"template": args.template, "variant": args.variant, "image": str(image_path), "obstacles": obstacles, "safe_boxes": safe_boxes, "alignment_guides": guides, "violations": violations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"visualized {len(safe_boxes)} safe boxes -> {args.output}")


if __name__ == "__main__":
    main()
