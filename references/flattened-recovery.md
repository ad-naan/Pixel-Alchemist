# Flattened-image text recovery

## Contents

1. Limits and guarantees
2. Analysis specification
3. Mask strategy
4. Typography matching
5. Reconstruction and verification
6. Production procedure

## Limits and guarantees

A flattened image does not contain the pixels hidden under its text. Do not claim exact recovery without a clean or layered source.

The enforceable production guarantees are:

- preserve the source file;
- refine coarse OCR boxes into glyph/effect masks;
- change only approved mask pixels;
- report zero changed pixels outside the mask;
- rank typography candidates rather than inventing an exact font;
- retain analysis, masks, reports, and render specs for audit.

## Analysis specification

Run:

```powershell
python scripts\analyze_flattened_text.py finished.png recovery-spec.json --output-dir work\analysis
```

Minimal specification:

```json
{
  "safe_padding": [8, 10, 8, 10],
  "erase_expand": 4,
  "font_candidates": [
    {"path": "fonts/Body-Regular.ttf", "family": "Body", "weight": "regular"},
    {"path": "fonts/Body-Bold.ttf", "family": "Body", "weight": "bold"}
  ],
  "regions": [
    {
      "id": "headline",
      "search_box": [80, 120, 700, 220],
      "text": "Known original copy",
      "lines": ["Known original", "copy"],
      "fill_colors": ["#FFFFFF"],
      "stroke_colors": ["#14213D"],
      "shadow_colors": ["#000000"],
      "color_tolerance": 60,
      "min_font_size": 32,
      "max_font_size": 90
    }
  ]
}
```

`search_box` may come from OCR, vision inspection, or manual measurement. It is a search constraint, not an erase rectangle. `text` and `lines` enable font matching. Keep intentional line breaks explicit.

Global or region fields:

- `safe_padding`: left, top, right, bottom padding around observed effects.
- `erase_expand`: dilation radius covering antialiasing and compression halos.
- `font_candidates`: font paths with optional family and weight labels.
- `fill_colors`, `stroke_colors`, `shadow_colors`: target colors used for mask extraction.
- `color_tolerance`: RGB distance allowed around target colors.
- `minimum_component_area`: rejects isolated noise.
- `maximum_line_gap`: row-gap heuristic when explicit line count is unavailable.
- `fill_mask_path` or `mask_path`: externally prepared full-canvas or region-sized mask.
- `stroke_mask_path`, `shadow_mask_path`: optional effect masks from an external segmentation tool.

Use `@skill/` paths for bundled resources. Relative paths resolve from the specification directory.

## Mask strategy

Prefer methods in this order:

1. Supplied layer/vector mask.
2. High-confidence color segmentation inside a tight search box.
3. OCR/model mask refined against actual pixels.
4. Automatic local-contrast segmentation followed by manual preview inspection.

Include fill, stroke, shadow, glow, and visible compression halos in the erase mask. Keep the undilated ink mask for measurement and the expanded effect mask for erasure. Never erase the whole OCR rectangle when only glyph pixels require replacement.

For text over faces, products, fine geometry, reflections, or repeated texture, use an external segmentation/retouching step to produce the mask, then keep the byte-identical outside-mask verification.

## Typography matching

The analyzer renders the known text through every candidate font and size, compares dimensions and glyph shape, and returns ranked matches.

- Lower `score` is better.
- Higher `shape_iou` is better.
- Treat family/weight as reliable only when the candidate set contains plausible fonts.
- Treat size as an estimate when the source has scaling, perspective, blur, or compression.
- Validate the top matches by redrawing over the cleaned image at 100% zoom.

The report also includes observed fill/stroke colors, estimated stroke width, alignment, line boxes, safe box, and a `render_spec`. Text elements accept a direct `font_path`, so the matched candidate can be used without changing global language presets.

## Reconstruction and verification

Run:

```powershell
python scripts\erase_text_mask.py finished.png work\analysis\combined-erase-mask.png `
  --output work\cleaned.png --method auto
```

`auto` evaluates:

- `telea`: useful for continuous texture and small masks;
- `ns`: useful for smooth continuation and gradients;
- `polynomial`: useful for flat fields, lighting ramps, and simple surfaces.

The script composites reconstructed pixels only where the binary mask is nonzero. It raises an error if any outside pixel changes and writes:

- mask bounding box and pixel count;
- selected method and candidate seam scores;
- changed inside-pixel count;
- changed outside-mask count;
- `outside_mask_byte_identical`.

Pass `--ground-truth clean.png` only in tests. It produces an inside-mask MAE metric but never supplies pixels to reconstruction.

## Production procedure

1. Preserve the finished source.
2. Obtain copy and coarse boxes through project data, OCR, or inspection.
3. Prepare candidate fonts and effect colors.
4. Run analysis and inspect `measurement-preview.png`, ink masks, and erase masks.
5. Correct the narrowest failing region rather than broadening every mask.
6. Run reconstruction and require `outside_mask_byte_identical: true`.
7. Inspect seams at 100% and against dark/light display backgrounds.
8. Paste the emitted `render_spec` into the batch configuration.
9. Replace `fixed_text` with `value_key` for variants.
10. Render and compare typography, baseline, color, stroke, shadow, and visual center.
