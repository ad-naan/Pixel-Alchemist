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

`variants` are generic batch records. `id` determines the output folder. `language` selects fonts and shaping but is optional for non-text work. `values`, `assets`, `background`, `backgrounds`, `layout_overrides`, and `alignment_overrides` may vary independently.

`layout_overrides[template][element]` changes only that element in that template. `alignment_overrides[template][group]` changes only that template-local alignment group. Never put a language exception in the base template when only one variant and one template need it.

Legacy `locales` and `copy_key` remain accepted as aliases for `variants` and `value_key`.

Top-level assets merge in `default` → base language → full language → variant id order; variant-level `assets` win last. This supports any fallback scheme without duplicating templates.

## Templates own their coordinates

Treat every template as an independent measured composition. Reusing role names expresses semantic identity, not coordinate identity. Do not derive portrait coordinates by scaling landscape coordinates unless the supplied artwork proves that relationship.

```json
{
  "templates": {
    "landscape": {
      "canvas": [1600, 900],
      "elements": {
        "headline": {"type": "text", "value_key": "headline", "box": [84, 470, 620, 128]},
        "date": {"type": "text", "value_key": "date", "box": [84, 606, 500, 54]},
        "location": {"type": "icon_text", "value_key": "location", "box": [84, 674, 540, 48]}
      },
      "alignment_groups": {
        "main-copy": {
          "members": ["headline", "date", "location"],
          "edge": "left",
          "anchor_role": "headline"
        }
      }
    },
    "portrait": {
      "canvas": [1080, 1350],
      "elements": {
        "headline": {"type": "text", "value_key": "headline", "box": [594, 336, 414, 110]},
        "date": {"type": "text", "value_key": "date", "box": [594, 454, 390, 50]},
        "location": {"type": "icon_text", "value_key": "location", "box": [594, 518, 390, 44]}
      },
      "alignment_groups": {
        "main-copy": {
          "members": ["headline", "date", "location"],
          "edge": "left",
          "position": 594
        }
      }
    }
  }
}
```

An alignment group belongs to exactly one template. It may align `left`, `right`, or `center` and must provide exactly one reference:

- `anchor_role`: derive the target edge or centerline from one member's resolved element box after element overrides;
- `position`: use an explicit canvas coordinate for the edge or centerline.

Set the optional group-level `physical_align` to `left`, `center`, or `right` when all member text and `icon_text` elements must place their visible content against the same physical canvas edge. This does not change bidi shaping or reading direction.

`members` may contain text, `icon_text`, buttons, or image elements. Alignment groups resolve their element boxes before drawing; for `icon_text`, that box contains the complete compound unit. QA may then inspect the reported visible group or ink bounds. Alignment groups place elements; QA tolerances belong under `template.qa`, not inside the group.

## Template-local QA

Define acceptance rules beside the template whose geometry they inspect:

```json
{
  "qa": {
    "alignment_groups": [
      {"roles": ["headline", "date", "location"], "edge": "left", "metric": "ink_box", "tolerance": 2}
    ],
    "spacing": [
      {"roles": ["headline", "date"], "axis": "y", "min": 12}
    ],
    "non_overlap": [
      ["headline", "location"]
    ],
    "elements": {
      "headline": {"min_font_size": 34, "max_lines": 3, "containment_tolerance": 0},
      "location": {"containment_tolerance": 0}
    }
  }
}
```

The two `alignment_groups` fields have different jobs. `template.alignment_groups` is an object of named placement constraints and moves element boxes before rendering. `template.qa.alignment_groups` is a list of assertions over actual reported metrics and never moves content. QA roles need not duplicate one placement group exactly; use them to state the visible relationship that must pass.

Run QA against actual rendered ink, image, button, or compound group bounds. A configured element box is an available region, not proof that visible content is aligned or collision-free. Treat QA failures as production failures unless the current project explicitly approves an exception.

## Built-in elements

- `text`: fitted variable or fixed text. Supports direction, physical alignment, wrapping strategy, line limits, line height, stroke, and shadow.
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

Text elements may set `font_path` to use one exact font file instead of language-level font mapping. This is useful when `analyze_flattened_text.py` has matched a font candidate. Its `render_spec` output can be pasted into a template, then change `fixed_text` or replace it with `value_key` for batch variants.

### Text direction, placement, and wrapping

Keep these properties independent:

- `direction`: `auto`, `ltr`, or `rtl`; controls shaping, bidi order, and language-engine behavior.
- `physical_align`: `left`, `center`, or `right`; controls where the rendered ink sits in its box on the canvas.
- `wrap_strategy`: `auto`, `word`, `grapheme`, or `manual`; controls legal line-break candidates.

`auto` may infer RTL shaping from the language or text, but it must not silently change an explicit `physical_align`. Mixed Arabic/Latin text remains in logical Unicode order. `manual` accepts only supplied newlines. `grapheme` preserves combining sequences; use it as the safe fallback for Thai and other scripts when a language-aware word segmenter is unavailable. Explicit newlines remain immutable under every strategy.

```json
{
  "type": "text",
  "value_key": "headline",
  "box": [92, 120, 560, 150],
  "direction": "rtl",
  "physical_align": "left",
  "wrap_strategy": "auto",
  "max_font_size": 58,
  "min_font_size": 34,
  "max_lines": 3
}
```

This can shape a logical mixed string such as `تبقّى 4 أيام حتى Hall A في 2026` as RTL while keeping its visible block on a physically left-aligned design baseline.

### `icon_text` alignment

Use `physical_align` to place the complete measured icon-and-text unit inside its box, and `icon_side: start|end|left|right` to control the icon relative to logical or physical direction. `group_align` remains a backward-compatible fallback when `physical_align` is absent. The text is measured independently inside that compound unit. The alignment report includes `group_box`, `icon_box`, `text_box`, and `ink_box` so template alignment and collision QA can use the complete visible element.

For a flattened-only source, generate the full-canvas mask first:

```powershell
python scripts\analyze_flattened_text.py finished.png recovery-spec.json --output-dir work\analysis
python scripts\erase_text_mask.py finished.png work\analysis\combined-erase-mask.png `
  --output work\cleaned.png --method auto
```

Do not replace the precise mask with its rectangular bounding box. The eraser guarantees that pixels outside the supplied mask remain byte-identical.

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
