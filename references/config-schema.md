# Batch specification

Use one JSON file for font sources, asset fallbacks, templates, elements, and variants. Relative paths resolve from the JSON directory. Prefix bundled skill assets with `@skill/`.

```json
{
  "font_preset": "@skill/assets/font-presets.json",
  "fonts": {
    "default": {"regular": "fonts/Body-Regular.ttf", "bold": "fonts/Body-Bold.ttf"}
  },
  "assets": {
    "default": {"mark": "assets/default/mark.png"},
    "variant-b": {"mark": "assets/variant-b/mark.png"}
  },
  "templates": {
    "landscape": {
      "canvas": [1200, 628],
      "background": "backgrounds/landscape.png",
      "output": "landscape.png",
      "elements": {
        "remove_old_headline": {
          "type": "erase",
          "z": 0,
          "box": [70, 90, 620, 150],
          "method": "inpaint-telea",
          "radius": 4,
          "mask_expand": 2
        },
        "shade": {
          "type": "rect",
          "z": 10,
          "box": [50, 70, 680, 210],
          "color": "#10182899",
          "radius": 24
        },
        "mark": {
          "type": "image",
          "z": 20,
          "asset_key": "mark",
          "box": [80, 92, 92, 92],
          "fit": "contain",
          "opacity": 1.0,
          "rotation": 0
        },
        "headline": {
          "type": "text",
          "z": 30,
          "value_key": "headline",
          "box": [195, 88, 500, 110],
          "max_font_size": 54,
          "min_font_size": 24,
          "max_lines": 2,
          "weight": "bold",
          "align": "left",
          "color": "#FFFFFF",
          "stroke_width": 1,
          "stroke_color": "#00000066",
          "shadow_offset": [2, 3],
          "shadow_color": "#00000066"
        },
        "action": {
          "type": "button",
          "z": 40,
          "value_key": "action",
          "box": [80, 210, 300, 64],
          "max_font_size": 28,
          "min_font_size": 15,
          "max_lines": 1,
          "weight": "bold",
          "background": "#FF7A00",
          "text_color": "#FFFFFF",
          "radius": 32,
          "show_arrow": true,
          "drop_arrow_if_needed": true,
          "drop_arrow_below_size": 20
        }
      }
    }
  },
  "variants": [
    {
      "id": "variant-a",
      "language": "en",
      "values": {"headline": "First line\nSecond line", "action": "Continue"}
    },
    {
      "id": "variant-b",
      "language": "es",
      "values": {"headline": "Texto alternativo", "action": "Continuar"},
      "layout_overrides": {
        "landscape": {"headline": {"max_font_size": 48}}
      }
    }
  ]
}
```

## Variants

`variants` are generic batch records. `id` determines the output folder. `language` selects fonts and shaping but is optional for non-text work. `values`, `assets`, `background`, `backgrounds`, and `layout_overrides` may vary independently.

Legacy `locales` and `copy_key` remain accepted as aliases for `variants` and `value_key`.

Top-level assets merge in `default` → base language → full language → variant id order; variant-level `assets` win last. This supports any fallback scheme without duplicating templates.

## Built-in elements

- `text`: fitted variable or fixed text. Supports alignment, line limits, line height, stroke, and shadow.
- `image`: arbitrary raster or SVG asset with `contain`, `cover`, or `stretch`; supports opacity and rotation.
- `icon_text`: measured icon-and-text group with physical or logical icon sides; accepts `icon` or `icon_asset_key`.
- `button`: rounded shape, fitted label, vector arrow, and automatic arrow removal for long values.
- `rect`: solid/translucent rectangle with optional outline and corner radius.
- `ellipse`: filled or outlined ellipse.
- `polygon`: filled or outlined arbitrary point list.
- `line`: polyline with configurable color, width, and joint.
- `erase`: reconstruct a box, polygon, or mask using `solid`, `blur`, `inpaint-telea`, or `inpaint-ns`.

Elements render by ascending `z`; equal values retain JSON order. Set `enabled: false` in an override to suppress one element.

For `erase`, `mask_path` is a full-canvas grayscale mask; white pixels are replaced. `box` and `polygon` can be combined with the mask. Use `mask_expand` for antialiased remnants and `feather` for soft blending.

## Custom hooks

Pass `--hook project_hook.py` when a built-in element is insufficient:

```python
def before_frame(canvas, context): ...
def draw_element(canvas, role, spec, context): ...  # return metrics or None
def after_frame(canvas, context): ...
```

`context` contains the variant and id, language, template, values, resolved assets, fonts, config directory, and frame index/count. Returning metrics marks an element handled.

Use hooks for OCR-assisted masks, content-aware reconstruction beyond OpenCV inpainting, perspective/mesh transforms, clipping paths, advanced blend modes, generated QR/barcodes, procedural effects, synchronized multi-element animation, and external imaging tools. Keep reusable data and coordinates in JSON even when drawing is custom.

## Output and animation

Static outputs may be PNG, JPEG, WebP, or GIF. An animated GIF background produces a strict frame-for-frame GIF when the output suffix is `.gif`. Optional template `animation` fields let validation assert frame count, durations, and loop.
