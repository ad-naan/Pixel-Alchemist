from __future__ import annotations

import argparse
import importlib.util
import io
import json
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any

from PIL import GifImagePlugin, Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageSequence, features

try:
    from .layout import resolve_elements
except ImportError:
    from layout import resolve_elements


def language_key(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def is_rtl(text: str) -> bool:
    return any("\u0590" <= character <= "\u08ff" for character in text)


def resolved_direction(text: str, spec: dict[str, Any]) -> str:
    direction = str(spec.get("direction", "auto"))
    if direction not in {"auto", "ltr", "rtl"}:
        raise ValueError(f"unsupported text direction: {direction!r}")
    return "rtl" if direction == "auto" and is_rtl(text) else ("ltr" if direction == "auto" else direction)


def physical_alignment(text: str, spec: dict[str, Any]) -> str:
    if "physical_align" in spec:
        align = str(spec["physical_align"])
    else:
        align = str(spec.get("align", "left"))
        if align == "force-left":
            align = "left"
        elif is_rtl(text) and align == "left":
            align = "right"
    if align not in {"left", "center", "right"}:
        raise ValueError(f"unsupported physical alignment: {align!r}")
    return align


def text_kwargs(text: str, language: str, spec: dict[str, Any]) -> dict[str, str]:
    direction = resolved_direction(text, spec)
    explicit_direction = str(spec.get("direction", "auto")) != "auto"
    if direction == "rtl" or explicit_direction:
        if not features.check("raqm"):
            raise RuntimeError("explicit or RTL text direction requires Pillow RAQM support")
        kwargs = {"direction": direction}
        shaping_language = language_key(language).split("-", 1)[0]
        if shaping_language != "default":
            kwargs["language"] = shaping_language
        return kwargs
    return {}


def resolve_path(value: str, base_dir: Path) -> Path:
    if value.startswith("@skill/"):
        return (Path(__file__).resolve().parent.parent / value.removeprefix("@skill/")).resolve()
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def load_fonts(payload: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    fonts: dict[str, Any] = {}
    preset_value = payload.get("font_preset")
    if preset_value:
        preset_path = resolve_path(str(preset_value), base_dir)
        preset_payload = json.loads(preset_path.read_text(encoding="utf-8"))
        fonts.update(preset_payload.get("fonts", preset_payload))
    for language, weights in payload.get("fonts", {}).items():
        fonts[language] = {**fonts.get(language, {}), **weights}
    return fonts


def font_path(fonts: dict[str, Any], language: str, weight: str, base_dir: Path) -> Path:
    full = language_key(language)
    base = full.split("-", 1)[0]
    for key in (full, base, "default"):
        spec = fonts.get(key)
        if isinstance(spec, dict) and spec.get(weight):
            path = resolve_path(str(spec[weight]), base_dir)
            if not path.exists():
                raise FileNotFoundError(f"font does not exist: {path}")
            return path
    raise ValueError(f"no {weight} font configured for {language}")


def load_font(fonts: dict[str, Any], language: str, weight: str, size: int, base_dir: Path) -> ImageFont.FreeTypeFont:
    engine = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    return ImageFont.truetype(str(font_path(fonts, language, weight, base_dir)), size, layout_engine=engine)


def load_element_font(spec: dict[str, Any], fonts: dict[str, Any], language: str, weight: str, size: int, base_dir: Path) -> ImageFont.FreeTypeFont:
    direct_path = spec.get("font_path")
    if not direct_path:
        return load_font(fonts, language, weight, size, base_dir)
    path = resolve_path(str(direct_path), base_dir)
    if not path.exists():
        raise FileNotFoundError(f"font does not exist: {path}")
    engine = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    return ImageFont.truetype(str(path), size, layout_engine=engine)


def load_rgba_asset(path: Path) -> Image.Image:
    if path.suffix.lower() == ".svg":
        try:
            from affine import Affine
            from resvg import render, usvg

            options = usvg.Options.default()
            options.load_system_fonts()
            tree = usvg.Tree.from_str(path.read_text(encoding="utf-8"), options)
            png_data = bytes(render(tree, Affine.identity()[0:6]))
        except Exception as resvg_error:
            try:
                import cairosvg

                png_data = cairosvg.svg2png(url=str(path))
            except Exception as cairo_error:
                raise RuntimeError(f"SVG rendering failed with resvg ({resvg_error}) and CairoSVG ({cairo_error})") from cairo_error
        with Image.open(io.BytesIO(png_data)) as image:
            return image.convert("RGBA")
    with Image.open(path) as image:
        return image.convert("RGBA")


def measured_box(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, language: str, spec: dict[str, Any], stroke_width: int = 0) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width, **text_kwargs(text, language, spec))


def width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, language: str, spec: dict[str, Any]) -> int:
    box = measured_box(draw, text, font, language, spec)
    return box[2] - box[0]


def is_variation_selector(character: str) -> bool:
    value = ord(character)
    return 0xFE00 <= value <= 0xFE0F or 0xE0100 <= value <= 0xE01EF


def grapheme_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    for character in text:
        extends_previous = bool(clusters) and (
            unicodedata.combining(character) != 0
            or unicodedata.category(character).startswith("M")
            or is_variation_selector(character)
            or character == "\u200d"
            or clusters[-1].endswith("\u200d")
        )
        if extends_previous:
            clusters[-1] += character
        else:
            clusters.append(character)
    return clusters


def wrap_units(draw: ImageDraw.ImageDraw, units: list[str], separator: str, font: ImageFont.FreeTypeFont, max_width: int, language: str, spec: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current}{separator}{unit}"
        if current and width(draw, candidate, font, language, spec) > max_width:
            lines.append(current.rstrip())
            current = unit.lstrip() if not separator else unit
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return lines or [""]


def wrap_paragraph(draw: ImageDraw.ImageDraw, paragraph: str, font: ImageFont.FreeTypeFont, max_width: int, language: str, spec: dict[str, Any]) -> list[str]:
    if not paragraph:
        return [""]
    strategy = str(spec.get("wrap_strategy", "auto"))
    if strategy not in {"auto", "word", "grapheme", "manual"}:
        raise ValueError(f"unsupported wrap strategy: {strategy!r}")
    if strategy == "manual":
        return [paragraph]
    words = paragraph.split()
    use_words = strategy == "word" or (
        strategy == "auto"
        and len(words) > 1
        and all(width(draw, word, font, language, spec) <= max_width for word in words)
    )
    units = words if use_words else grapheme_clusters(paragraph)
    return wrap_units(draw, units, " " if use_words else "", font, max_width, language, spec)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, language: str, spec: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(wrap_paragraph(draw, paragraph, font, max_width, language, spec))
    return lines


def fit_text(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    language: str,
    spec: dict[str, Any],
    fonts: dict[str, Any],
    base_dir: Path,
) -> dict[str, Any]:
    x, y, box_width, box_height = (int(value) for value in spec["box"])
    weight = str(spec.get("weight", "regular"))
    max_lines = int(spec.get("max_lines", 1))
    line_height = float(spec.get("line_height", 1.12))
    stroke_width = int(spec.get("stroke_width", 0))
    for size in range(int(spec["max_font_size"]), int(spec["min_font_size"]) - 1, -1):
        font = load_element_font(spec, fonts, language, weight, size, base_dir)
        lines = wrap_text(draw, text, font, box_width, language, spec)
        if len(lines) > max_lines:
            continue
        boxes = [measured_box(draw, line, font, language, spec, stroke_width) for line in lines]
        line_widths = [box[2] - box[0] for box in boxes]
        line_heights = [box[3] - box[1] for box in boxes]
        gap = max(0, round(size * (line_height - 1.0)))
        total_height = sum(line_heights) + gap * max(0, len(lines) - 1)
        if total_height <= box_height and all(value <= box_width for value in line_widths):
            return {
                "font": font,
                "font_size": size,
                "lines": lines,
                "boxes": boxes,
                "line_heights": line_heights,
                "line_widths": line_widths,
                "gap": gap,
                "total_height": total_height,
                "box": [x, y, box_width, box_height],
            }
    raise ValueError(f"{language} text does not fit {box_width}x{box_height}: {text!r}")


def draw_text_element(
    canvas: Image.Image,
    *,
    text: str,
    language: str,
    spec: dict[str, Any],
    fonts: dict[str, Any],
    base_dir: Path,
) -> dict[str, Any]:
    draw = ImageDraw.Draw(canvas)
    fit = fit_text(draw, text=text, language=language, spec=spec, fonts=fonts, base_dir=base_dir)
    x, y, box_width, box_height = fit["box"]
    cursor_y = y + (box_height - fit["total_height"]) / 2
    align = physical_alignment(text, spec)
    direction = resolved_direction(text, spec)
    stroke_width = int(spec.get("stroke_width", 0))
    shadow_offset = spec.get("shadow_offset", [0, 0])
    shadow_x, shadow_y = (int(value) for value in shadow_offset)
    shadow_fill = spec.get("shadow_color")
    line_boxes = []
    for line, box, line_width, line_height in zip(fit["lines"], fit["boxes"], fit["line_widths"], fit["line_heights"]):
        if align == "center":
            draw_x = x + (box_width - line_width) / 2
        elif align == "right":
            draw_x = x + box_width - line_width
        else:
            draw_x = x
        position = (draw_x - box[0], cursor_y - box[1])
        line_boxes.append([round(draw_x), round(cursor_y), line_width, line_height])
        if shadow_fill and (shadow_x or shadow_y):
            draw.text(
                (position[0] + shadow_x, position[1] + shadow_y),
                line,
                font=fit["font"],
                fill=shadow_fill,
                stroke_width=stroke_width,
                stroke_fill=shadow_fill,
                **text_kwargs(text, language, spec),
            )
        draw.text(
            position,
            line,
            font=fit["font"],
            fill=spec.get("color", "#FFFFFF"),
            stroke_width=stroke_width,
            stroke_fill=spec.get("stroke_color", spec.get("color", "#FFFFFF")),
            **text_kwargs(text, language, spec),
        )
        cursor_y += line_height + fit["gap"]
    ink_left = min(box[0] for box in line_boxes)
    ink_top = min(box[1] for box in line_boxes)
    ink_right = max(box[0] + box[2] for box in line_boxes)
    ink_bottom = max(box[1] + box[3] for box in line_boxes)
    max_font_size = int(spec["max_font_size"])
    max_lines = int(spec.get("max_lines", 1))
    return {
        "box": fit["box"],
        "safe_box": fit["box"],
        "ink_box": [ink_left, ink_top, ink_right - ink_left, ink_bottom - ink_top],
        "line_boxes": line_boxes,
        "font_size": fit["font_size"],
        "max_font_size": max_font_size,
        "font_scale": fit["font_size"] / max_font_size,
        "lines": fit["lines"],
        "line_count": len(fit["lines"]),
        "max_lines": max_lines,
        "content_height": fit["total_height"],
        "height_density": fit["total_height"] / box_height,
        "direction": direction,
        "physical_align": align,
    }


def paste_asset(
    canvas: Image.Image,
    asset: Image.Image,
    box: list[int],
    fit: str = "contain",
    opacity: float = 1.0,
    rotation: float = 0.0,
) -> dict[str, Any]:
    x, y, box_width, box_height = (int(value) for value in box)
    if rotation:
        asset = asset.rotate(float(rotation), expand=True, resample=Image.Resampling.BICUBIC)
    opacity = max(0.0, min(1.0, float(opacity)))
    if opacity < 1.0:
        asset = asset.copy()
        asset.putalpha(asset.getchannel("A").point(lambda value: round(value * opacity)))
    if fit == "stretch":
        resized = asset.resize((box_width, box_height), Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, (x, y))
        return {"box": [x, y, box_width, box_height], "safe_box": [x, y, box_width, box_height], "ink_box": [x, y, box_width, box_height], "rendered_size": [box_width, box_height], "fit": fit, "opacity": opacity, "rotation": rotation}
    if fit not in {"contain", "cover"}:
        raise ValueError(f"unsupported image fit: {fit}")
    scale_fn = min if fit == "contain" else max
    scale = scale_fn(box_width / asset.width, box_height / asset.height)
    size = (max(1, round(asset.width * scale)), max(1, round(asset.height * scale)))
    resized = asset.resize(size, Image.Resampling.LANCZOS)
    if fit == "cover":
        left = max(0, (size[0] - box_width) // 2)
        top = max(0, (size[1] - box_height) // 2)
        resized = resized.crop((left, top, left + box_width, top + box_height))
        position = (x, y)
    else:
        position = (x + (box_width - size[0]) // 2, y + (box_height - size[1]) // 2)
    canvas.alpha_composite(resized, position)
    rendered_box = [position[0], position[1], resized.width, resized.height]
    return {"box": [x, y, box_width, box_height], "safe_box": [x, y, box_width, box_height], "ink_box": rendered_box, "rendered_size": list(resized.size), "fit": fit, "opacity": opacity, "rotation": rotation}


def draw_icon_text(
    canvas: Image.Image,
    *,
    text: str,
    language: str,
    spec: dict[str, Any],
    fonts: dict[str, Any],
    base_dir: Path,
) -> dict[str, Any]:
    icon_path = resolve_path(str(spec["icon"]), base_dir)
    icon = load_rgba_asset(icon_path)
    x, y, box_width, box_height = (int(value) for value in spec["box"])
    icon_width, icon_height = (int(value) for value in spec["icon_size"])
    gap = int(spec.get("icon_gap", 8))
    text_spec = {**spec, "box": [0, 0, box_width - icon_width - gap, box_height], "physical_align": "left"}
    fit = fit_text(ImageDraw.Draw(canvas), text=text, language=language, spec=text_spec, fonts=fonts, base_dir=base_dir)
    text_width = max(fit["line_widths"])
    group_width = icon_width + gap + text_width
    group_align = str(spec.get("physical_align", spec.get("group_align", "left")))
    if group_align == "force-left":
        group_align = "left"
    if group_align not in {"left", "center", "right"}:
        raise ValueError(f"unsupported icon-text physical alignment: {group_align!r}")
    if group_align == "right":
        group_x = x + box_width - group_width
    elif group_align == "center":
        group_x = x + (box_width - group_width) / 2
    else:
        group_x = x
    direction = resolved_direction(text, spec)
    icon_side = str(spec.get("icon_side", "left"))
    if icon_side == "start":
        icon_side = "right" if direction == "rtl" else "left"
    elif icon_side == "end":
        icon_side = "left" if direction == "rtl" else "right"
    if icon_side == "right":
        text_x = group_x
        icon_x = group_x + text_width + gap
    else:
        icon_x = group_x
        text_x = group_x + icon_width + gap
    icon_box = [round(icon_x), y + (box_height - icon_height) // 2, icon_width, icon_height]
    paste_asset(canvas, icon, icon_box)
    text_box = [round(text_x), y, max(1, round(text_width + 2)), box_height]
    draw_spec = {**spec, "box": text_box, "physical_align": "left"}
    metrics = draw_text_element(canvas, text=text, language=language, spec=draw_spec, fonts=fonts, base_dir=base_dir)
    metrics["box"] = [x, y, box_width, box_height]
    metrics["safe_box"] = [x, y, box_width, box_height]
    metrics["group_box"] = [round(group_x), y, round(group_width), box_height]
    metrics["icon_box"] = icon_box
    metrics["text_box"] = text_box
    metrics["direction"] = direction
    metrics["physical_align"] = group_align
    return metrics


def draw_rect(canvas: Image.Image, spec: dict[str, Any]) -> dict[str, Any]:
    x, y, box_width, box_height = (int(value) for value in spec["box"])
    draw = ImageDraw.Draw(canvas, "RGBA")
    fill = ImageColor.getcolor(str(spec.get("color", "#00000000")), "RGBA")
    outline_value = spec.get("outline")
    outline = ImageColor.getcolor(str(outline_value), "RGBA") if outline_value else None
    radius = int(spec.get("radius", 0))
    xy = (x, y, x + box_width, y + box_height)
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=int(spec.get("outline_width", 1)))
    return {"box": [x, y, box_width, box_height], "safe_box": [x, y, box_width, box_height], "ink_box": [x, y, box_width, box_height]}


def draw_shape(canvas: Image.Image, kind: str, spec: dict[str, Any]) -> dict[str, Any]:
    draw = ImageDraw.Draw(canvas, "RGBA")
    fill_value = spec.get("color", "#00000000")
    fill = ImageColor.getcolor(str(fill_value), "RGBA") if fill_value is not None else None
    outline_value = spec.get("outline")
    outline = ImageColor.getcolor(str(outline_value), "RGBA") if outline_value else None
    line_width = int(spec.get("width", spec.get("outline_width", 1)))
    if kind == "ellipse":
        x, y, width, height = (int(value) for value in spec["box"])
        draw.ellipse((x, y, x + width, y + height), fill=fill, outline=outline, width=line_width)
        return {"box": [x, y, width, height], "safe_box": [x, y, width, height], "ink_box": [x, y, width, height]}
    points = [(int(point[0]), int(point[1])) for point in spec["points"]]
    if kind == "polygon":
        draw.polygon(points, fill=fill, outline=outline)
    elif kind == "line":
        draw.line(points, fill=outline or fill, width=line_width, joint=str(spec.get("joint", "curve")))
    else:
        raise ValueError(f"unsupported shape: {kind}")
    left = min(point[0] for point in points)
    top = min(point[1] for point in points)
    right = max(point[0] for point in points)
    bottom = max(point[1] for point in points)
    return {"points": [list(point) for point in points], "ink_box": [left, top, right - left, bottom - top]}


def region_mask(canvas: Image.Image, spec: dict[str, Any], base_dir: Path) -> Image.Image:
    mask = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(mask)
    if spec.get("mask_path"):
        import numpy as np

        with Image.open(resolve_path(str(spec["mask_path"]), base_dir)) as source:
            external = source.convert("L")
        if external.size != canvas.size:
            external = external.resize(canvas.size, Image.Resampling.NEAREST)
        mask = Image.fromarray(np.maximum(np.array(mask), np.array(external)).astype("uint8"))
        draw = ImageDraw.Draw(mask)
    if spec.get("box"):
        x, y, width, height = (int(value) for value in spec["box"])
        draw.rectangle((x, y, x + width, y + height), fill=255)
    if spec.get("polygon"):
        draw.polygon([(int(point[0]), int(point[1])) for point in spec["polygon"]], fill=255)
    expand = int(spec.get("mask_expand", 0))
    if expand > 0:
        mask = mask.filter(ImageFilter.MaxFilter(expand * 2 + 1))
    feather = float(spec.get("feather", 0))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    return mask


def erase_region(canvas: Image.Image, spec: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    mask = region_mask(canvas, spec, base_dir)
    method = str(spec.get("method", "solid"))
    if method == "solid":
        replacement = Image.new("RGBA", canvas.size, ImageColor.getcolor(str(spec.get("color", "#000000")), "RGBA"))
    elif method == "blur":
        replacement = canvas.filter(ImageFilter.GaussianBlur(float(spec.get("radius", 12))))
    elif method in {"inpaint-telea", "inpaint-ns"}:
        try:
            import cv2
            import numpy as np
        except ImportError as error:
            raise RuntimeError("OpenCV and NumPy are required for inpainting") from error
        rgba = np.array(canvas)
        rgb = cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB)
        mask_array = np.array(mask)
        algorithm = cv2.INPAINT_TELEA if method == "inpaint-telea" else cv2.INPAINT_NS
        restored = cv2.inpaint(rgb, mask_array, float(spec.get("radius", 3)), algorithm)
        restored_rgba = np.dstack((restored, rgba[:, :, 3]))
        replacement = Image.fromarray(restored_rgba.astype("uint8"), "RGBA")
    else:
        raise ValueError(f"unsupported erase method: {method}")
    canvas.paste(replacement, (0, 0), mask)
    bbox = mask.getbbox()
    return {"method": method, "mask_bbox": list(bbox) if bbox else None}


def draw_button(
    canvas: Image.Image,
    *,
    text: str,
    language: str,
    spec: dict[str, Any],
    fonts: dict[str, Any],
    base_dir: Path,
) -> dict[str, Any]:
    x, y, box_width, box_height = (int(value) for value in spec["box"])
    padding_x = int(spec.get("padding_x", round(box_height * 0.36)))
    arrow_gap = int(spec.get("arrow_gap", round(box_height * 0.15)))
    wants_arrow = bool(spec.get("show_arrow", True))
    arrow_reserve = int(spec.get("arrow_reserve", round(box_height * 0.52))) if wants_arrow else 0
    candidates = [wants_arrow]
    if wants_arrow and spec.get("drop_arrow_if_needed", True):
        candidates.append(False)
    selected_arrow = False
    selected_fit = None
    for candidate in candidates:
        reserve = arrow_reserve + arrow_gap if candidate else 0
        text_spec = {
            **spec,
            "box": [x + padding_x, y, max(1, box_width - padding_x * 2 - reserve), box_height],
            "align": spec.get("text_align", "center"),
            "max_lines": int(spec.get("max_lines", 1)),
        }
        try:
            selected_fit = fit_text(ImageDraw.Draw(canvas), text=text, language=language, spec=text_spec, fonts=fonts, base_dir=base_dir)
            drop_below = spec.get("drop_arrow_below_size")
            if candidate and drop_below is not None and selected_fit["font_size"] < int(drop_below):
                continue
            selected_arrow = bool(candidate)
            break
        except ValueError:
            continue
    if selected_fit is None:
        raise ValueError(f"button label does not fit: {text!r}")
    draw_rect(canvas, {**spec, "color": spec.get("background", spec.get("color", "#F79331"))})
    reserve = arrow_reserve + arrow_gap if selected_arrow else 0
    label_spec = {
        **spec,
        "box": [x + padding_x, y, max(1, box_width - padding_x * 2 - reserve), box_height],
        "align": spec.get("text_align", "center"),
        "color": spec.get("text_color", "#FFFFFF"),
        "max_lines": int(spec.get("max_lines", 1)),
    }
    metrics = draw_text_element(canvas, text=text, language=language, spec=label_spec, fonts=fonts, base_dir=base_dir)
    if selected_arrow:
        arrow_center_x = x + box_width - padding_x - arrow_reserve / 2
        arrow_center_y = y + box_height / 2
        arrow_width = max(8, round(arrow_reserve * 0.45))
        arrow_head = max(4, round(arrow_width * 0.28))
        direction = str(spec.get("arrow_direction", "right"))
        sign = -1 if direction == "left" else 1
        start_x = arrow_center_x - sign * arrow_width / 2
        end_x = arrow_center_x + sign * arrow_width / 2
        arrow_color = spec.get("text_color", "#FFFFFF")
        arrow_draw = ImageDraw.Draw(canvas)
        line_width = max(1, int(spec.get("arrow_width", round(box_height * 0.035))))
        arrow_draw.line((start_x, arrow_center_y, end_x, arrow_center_y), fill=arrow_color, width=line_width)
        arrow_draw.line((end_x, arrow_center_y, end_x - sign * arrow_head, arrow_center_y - arrow_head), fill=arrow_color, width=line_width)
        arrow_draw.line((end_x, arrow_center_y, end_x - sign * arrow_head, arrow_center_y + arrow_head), fill=arrow_color, width=line_width)
    metrics["arrow_drawn"] = bool(selected_arrow)
    metrics["button_box"] = [x, y, box_width, box_height]
    return metrics


def load_hook(path: Path | None) -> ModuleType | None:
    if path is None:
        return None
    resolved = path.resolve()
    module_spec = importlib.util.spec_from_file_location("batch_image_hook", resolved)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"cannot load hook: {resolved}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def variant_identifier(variant: dict[str, Any]) -> str:
    return str(variant.get("id") or variant.get("language") or "default")


def resolved_assets(asset_catalog: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    language = language_key(str(variant.get("language", "default")))
    base = language.split("-", 1)[0]
    identifier = variant_identifier(variant)
    assets: dict[str, Any] = {}
    for key in ("default", base, language, identifier):
        value = asset_catalog.get(key, {})
        if isinstance(value, dict):
            assets.update(value)
    assets.update(variant.get("assets", {}))
    return assets


def render_frame(
    frame: Image.Image,
    *,
    template_name: str,
    template: dict[str, Any],
    variant: dict[str, Any],
    fonts: dict[str, Any],
    asset_catalog: dict[str, Any],
    base_dir: Path,
    hook: ModuleType | None = None,
    frame_index: int = 0,
    frame_count: int = 1,
) -> tuple[Image.Image, dict[str, Any]]:
    canvas = frame.convert("RGBA")
    language = str(variant.get("language", "default"))
    values = variant.get("values", variant.get("copy", {}))
    assets = resolved_assets(asset_catalog, variant)
    metrics = {}
    resolved_element_specs = resolve_elements(template_name, template, variant)
    context = {
        "variant": variant,
        "variant_id": variant_identifier(variant),
        "language": language,
        "template_name": template_name,
        "template": template,
        "resolved_elements": resolved_element_specs,
        "values": values,
        "copy": values,
        "assets": assets,
        "fonts": fonts,
        "base_dir": base_dir,
        "frame_index": frame_index,
        "frame_count": frame_count,
    }
    if hook and callable(getattr(hook, "before_frame", None)):
        hook.before_frame(canvas, context)
    ordered_elements = list(resolved_element_specs.items())
    ordered_elements.sort(key=lambda item: int(item[1].get("z", 0)))
    for role, spec in ordered_elements:
        if not bool(spec.get("enabled", True)):
            continue
        kind = str(spec["type"])
        if hook and callable(getattr(hook, "draw_element", None)):
            custom_metrics = hook.draw_element(canvas, role, spec, context)
            if custom_metrics is not None:
                metrics[role] = custom_metrics
                continue
        if kind in {"text", "icon_text", "button"}:
            value_key = str(spec.get("value_key", spec.get("copy_key", role)))
            text = str(spec.get("fixed_text") or values.get(value_key, "")).strip()
            if not text:
                continue
            text_language = str(spec.get("fixed_language", "en")) if spec.get("fixed_text") else language
            if kind == "text":
                metrics[role] = draw_text_element(canvas, text=text, language=text_language, spec=spec, fonts=fonts, base_dir=base_dir)
            elif kind == "icon_text":
                icon_value = assets.get(str(spec.get("icon_asset_key", ""))) or spec.get("icon")
                if not icon_value:
                    raise ValueError(f"missing icon for {template_name}.{role}")
                spec = {**spec, "icon": icon_value}
                metrics[role] = draw_icon_text(canvas, text=text, language=text_language, spec=spec, fonts=fonts, base_dir=base_dir)
            else:
                metrics[role] = draw_button(canvas, text=text, language=text_language, spec=spec, fonts=fonts, base_dir=base_dir)
        elif kind == "image":
            value = assets.get(str(spec.get("asset_key", role))) or spec.get("path")
            if value:
                image = load_rgba_asset(resolve_path(str(value), base_dir))
                metrics[role] = paste_asset(
                    canvas,
                    image,
                    spec["box"],
                    str(spec.get("fit", "contain")),
                    float(spec.get("opacity", 1.0)),
                    float(spec.get("rotation", 0.0)),
                )
        elif kind == "rect":
            metrics[role] = draw_rect(canvas, spec)
        elif kind in {"ellipse", "polygon", "line"}:
            metrics[role] = draw_shape(canvas, kind, spec)
        elif kind == "erase":
            metrics[role] = erase_region(canvas, spec, base_dir)
        else:
            raise ValueError(f"unsupported element type {kind!r} for {template_name}.{role}")
    if hook and callable(getattr(hook, "after_frame", None)):
        hook.after_frame(canvas, context)
    return canvas, metrics


def save_gif_exact(
    output: Path,
    frames: list[Image.Image],
    durations: list[int],
    disposals: list[int],
    loop: int,
) -> None:
    """Write every supplied frame; Pillow's public save path coalesces identical frames."""
    normalized: list[tuple[Image.Image, dict[str, Any]]] = []
    for index, frame in enumerate(frames):
        image = GifImagePlugin._normalize_mode(frame.copy())
        encoderinfo: dict[str, Any] = {
            "duration": durations[index],
            "disposal": disposals[index],
            "optimize": False,
        }
        if "transparency" in image.info:
            encoderinfo["transparency"] = image.info["transparency"]
        image = GifImagePlugin._normalize_palette(image, None, encoderinfo)
        normalized.append((image, encoderinfo))
    with output.open("wb") as stream:
        header_info = {**normalized[0][1], "loop": loop}
        for block in GifImagePlugin._get_global_header(normalized[0][0], header_info):
            stream.write(block)
        for index, (image, encoderinfo) in enumerate(normalized):
            if index:
                encoderinfo["include_color_table"] = True
            GifImagePlugin._write_frame_data(stream, image, (0, 0), encoderinfo)
        stream.write(b";")


def save_rendered(background: Path, output: Path, render: Any) -> dict[str, Any]:
    with Image.open(background) as source:
        frame_count = int(getattr(source, "n_frames", 1))
        if output.suffix.lower() != ".gif" or frame_count == 1:
            frame, metrics = render(source.convert("RGBA"), 0, 1)
            output.parent.mkdir(parents=True, exist_ok=True)
            suffix = output.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                frame.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
            elif suffix == ".gif":
                frame.save(output, format="GIF", save_all=False)
            elif suffix == ".webp":
                frame.save(output, format="WEBP", quality=95, method=6)
            else:
                frame.save(output, format="PNG", optimize=True)
            return metrics
        frames = []
        durations = []
        disposals = []
        metrics = {}
        for index, source_frame in enumerate(ImageSequence.Iterator(source)):
            frame, frame_metrics = render(source_frame.convert("RGBA"), index, frame_count)
            frames.append(frame)
            durations.append(int(source_frame.info.get("duration", source.info.get("duration", 100))))
            disposals.append(int(getattr(source_frame, "disposal_method", source.info.get("disposal", 2))))
            if index == 0:
                metrics = frame_metrics
        output.parent.mkdir(parents=True, exist_ok=True)
        save_gif_exact(output, frames, durations, disposals, int(source.info.get("loop", 0)))
        metrics["animation"] = {
            "frames": len(frames),
            "durations_ms": durations,
            "disposals": disposals,
            "loop": int(source.info.get("loop", 0)),
        }
        return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-edit image elements in static images and GIFs from a JSON specification.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--variants", nargs="*", help="Variant ids to render.")
    parser.add_argument("--languages", nargs="*", help="Backward-compatible alias for language variants.")
    parser.add_argument("--templates", nargs="*")
    parser.add_argument("--hook", type=Path, help="Optional project-specific Python hook module.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    hook = load_hook(args.hook)
    base_dir = args.config.resolve().parent
    fonts = load_fonts(payload, base_dir)
    requested_values = args.variants or args.languages
    requested_variants = {language_key(value) for value in requested_values} if requested_values else None
    requested_templates = set(args.templates) if args.templates else None
    report = []
    variants = payload.get("variants") or payload.get("locales") or [
        {"id": "default", "language": "default", "values": payload.get("values", {})}
    ]
    for variant in variants:
        identifier = variant_identifier(variant)
        language = str(variant.get("language", "default"))
        if requested_variants is not None and language_key(identifier) not in requested_variants and language_key(language) not in requested_variants:
            continue
        for template_name, template in payload.get("templates", {}).items():
            if requested_templates is not None and template_name not in requested_templates:
                continue
            background_name = variant.get("backgrounds", {}).get(template_name) or variant.get("background") or template["background"]
            background = args.background_dir / str(background_name)
            output = args.output_dir / identifier / str(template["output"])
            if output.exists() and not args.force:
                report.append({"variant": identifier, "language": language, "template": template_name, "input": str(background), "output": str(output), "status": "skipped"})
                continue
            with Image.open(background) as image:
                if image.size != tuple(template["canvas"]):
                    raise ValueError(f"{template_name}: {image.size} != {tuple(template['canvas'])}")
            metrics = save_rendered(
                background,
                output,
                lambda frame, frame_index, frame_count: render_frame(
                    frame,
                    template_name=template_name,
                    template=template,
                    variant=variant,
                    fonts=fonts,
                    asset_catalog=payload.get("assets", {}),
                    base_dir=base_dir,
                    hook=hook,
                    frame_index=frame_index,
                    frame_count=frame_count,
                ),
            )
            report.append({"variant": identifier, "language": language, "template": template_name, "input": str(background), "output": str(output), "status": "rendered", "metrics": metrics})
            print(f"[done] {identifier} {template_name}", flush=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(report)} outputs -> {args.output_dir}")


if __name__ == "__main__":
    main()
