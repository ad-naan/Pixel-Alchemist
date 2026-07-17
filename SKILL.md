---
name: pixel-alchemist
description: Batch inspect, measure, remove, replace, and render elements in arbitrary static images and animated GIFs. Use for bulk image production involving text replacement, multilingual typography, logos, icons, products, prices, dates, buttons, QR/image assets, shapes, masks, inpainting, layout adaptation, per-variant data, frame-by-frame animation, or visual QA across many sizes and outputs.
---

# Pixel Alchemist

Build deterministic batches from arbitrary source images using project data, measured layouts, and reusable rendering primitives.

## Workflow

1. Inventory inputs with `scripts/inventory_assets.py`. Classify flat images, clean backgrounds, references, layered assets, fonts, spreadsheets, vectors, masks, and animations.
2. Choose the safest source strategy: edit a clean/layered source; otherwise mask and reconstruct the old region before drawing replacements. Never cover old text blindly when texture or lighting must continue underneath.
3. Measure reference-versus-clean differences with `scripts/measure_reference_diff.py`. Generate annotated previews and convert observed ink bounds into padded safe boxes. Visualize configured safe boxes with `scripts/visualize_layout.py` before final rendering.
4. Extract batch data from the supplied workbook or JSON. Model each output as a generic `variant`; variants may represent languages, products, regions, dates, prices, channels, or any combination.
5. Define templates and ordered elements in JSON using `references/config-schema.md`. Keep coordinates, copy, assets, effects, and per-variant overrides out of renderer code.
6. Validate fonts and complex shaping with `scripts/check_text_runtime.py`. Reuse `assets/font-presets.json` when appropriate, but let project fonts override it.
7. Render with `scripts/render_batch.py`. Use built-in elements for normal work and a project hook for custom masks, blend modes, perspective transforms, coordinated motion, procedural graphics, or timeline behavior.
8. Validate coverage, sizes, frames, durations, disposal, and loops with `scripts/validate_outputs.py`.
9. Inspect representative extremes: smallest canvas, largest canvas, longest text, densest composition, complex script, transparent source, and animated source.
10. Write results only to a new output directory. Preserve inputs and emit `render-report.json`.

## Non-negotiable rules

- Prefer reversible compositing from clean sources. Use explicit masks and inpainting only when clean pixels are unavailable.
- Preserve intentional newlines before automatic wrapping. Fit by wrapping and reducing font size; never distort glyphs horizontally.
- Keep fixed content fixed only when the current request identifies it as fixed.
- Apply corrections at the narrowest scope: element, template, then variant. Do not globally shrink or move unrelated outputs.
- Require RAQM for Arabic and other bidirectional shaping. Never reverse Unicode strings manually.
- Treat icons, logos, QR codes, and product cutouts as generic image assets with default and variant-specific fallbacks.
- Preserve GIF frame count, timing, disposal, transparency, and loop. Draw on every affected frame.
- Put exceptional behavior in `before_frame`, `draw_element`, or `after_frame` hooks instead of forking the generic renderer.
- Fail visibly on missing fonts, missing assets, overflow, unsupported effects, or dimension mismatches. Never silently substitute or skip.

## References

- Read `references/config-schema.md` before creating or changing a batch specification.
- Read `references/typography-and-qa.md` for text shaping, wrapping, visual QA, flat-image reconstruction, and animation checks.
- Read `references/bundled-fonts.md` before selecting, replacing, or redistributing bundled fonts.

## Completion criteria

- Every requested variant has every requested template.
- Replaced regions contain no visible remnants of the old element.
- All elements remain inside intended safe areas without collisions.
- Typography, imagery, masks, colors, and effects match the current project's references.
- Static output dimensions and animated metadata match the specification.
- The report records input, output, chosen font sizes, line breaks, element metrics, and animation metadata.
