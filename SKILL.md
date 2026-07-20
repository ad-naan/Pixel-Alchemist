---
name: pixel-alchemist
description: Batch inspect, recover, measure, remove, replace, and render elements in arbitrary static images and animated GIFs. Use for bulk image production involving flattened-image text recovery, precise masks, typography estimation, text replacement, multilingual typography, logos, icons, products, prices, dates, buttons, QR/image assets, shapes, inpainting, layout adaptation, per-variant data, frame-by-frame animation, or pixel-level visual QA.
---

# Pixel Alchemist

Build deterministic batches from arbitrary source images using project data, measured layouts, and reusable rendering primitives.

## Workflow

1. Inventory inputs with `scripts/inventory_assets.py`. Classify flat images, clean backgrounds, references, layered assets, fonts, spreadsheets, vectors, masks, and animations.
2. Choose the safest source strategy. Use clean or layered sources when available. When only a flattened finished image exists, run `scripts/analyze_flattened_text.py` with known copy, search regions, colors, and candidate fonts; preserve its ink masks, effect masks, font matches, coordinates, and ready-to-paste render specs.
3. Reconstruct flattened regions with `scripts/erase_text_mask.py`. Require `outside_mask_byte_identical: true`; inspect seams before redrawing. Without a clean source, treat pixels under the old glyphs as an estimate rather than claiming the unknowable original background was recovered exactly.
4. When clean and finished references both exist, measure their differences with `scripts/measure_reference_diff.py`. Generate annotated previews and convert observed ink bounds into padded safe boxes. Measure every template independently: a landscape, portrait, square, banner, or animation may place the same semantic role at unrelated coordinates. Visualize configured safe boxes with `scripts/visualize_layout.py` before final rendering.
5. Extract batch data from the supplied workbook or JSON. Model each output as a generic `variant`; variants may represent languages, products, regions, dates, prices, channels, or any combination.
6. Define templates and ordered elements in JSON using `references/config-schema.md`. Keep coordinates, copy, assets, effects, and per-variant overrides out of renderer code. Put shared-edge and spacing constraints inside the template they govern; never use an alignment group to impose one coordinate across different templates.
7. Validate fonts and complex shaping with `scripts/check_text_runtime.py`. Reuse `assets/font-presets.json` when appropriate, but let project fonts override it.
8. Render with `scripts/render_batch.py`. Use built-in elements for normal work and a project hook for custom masks, blend modes, perspective transforms, coordinated motion, procedural graphics, or timeline behavior.
9. Validate coverage, sizes, frames, durations, disposal, loops, safe-area containment, template-local alignment groups, collisions, and minimum readable font sizes. Generate a QA grid for every template so variants can be compared as a matrix rather than one file at a time.
10. Inspect representative extremes: every template, smallest canvas, largest canvas, longest text, densest composition, mixed-direction text, Thai or another grapheme-sensitive script, transparent source, flattened-only source, and animated source.
11. Write results only to a new output directory. Preserve inputs and emit `render-report.json`.

## Non-negotiable rules

- Prefer reversible compositing from clean sources. Use explicit masks and inpainting only when clean pixels are unavailable.
- Change no pixel outside an approved flattened-image erase mask. Expand the mask to include antialiasing, stroke, shadow, glow, and compression halos before reconstruction.
- Treat exact font family and weight as candidate-matching results. Require known text plus candidate font files for strong identification; otherwise report estimates and confidence instead of inventing certainty.
- Preserve intentional newlines before automatic wrapping. Fit by wrapping and reducing font size; never distort glyphs horizontally.
- Keep text direction separate from physical placement. `direction` controls shaping and reading order; `physical_align` controls the visible left, center, or right edge of the element on the canvas.
- Wrap Thai and other combining-mark scripts by language-aware segments or grapheme clusters, never raw Unicode code points. Fail when the approved box and size range cannot hold valid lines.
- Keep fixed content fixed only when the current request identifies it as fixed.
- Apply corrections at the narrowest scope: base element, current template, then current variant's override for that template. Do not globally shrink or move unrelated templates or outputs.
- Require RAQM for Arabic and other bidirectional shaping. Never reverse Unicode strings manually.
- Treat icons, logos, QR codes, and product cutouts as generic image assets with default and variant-specific fallbacks.
- Preserve GIF frame count, timing, disposal, transparency, and loop. Draw on every affected frame.
- Put exceptional behavior in `before_frame`, `draw_element`, or `after_frame` hooks instead of forking the generic renderer.
- Fail visibly on missing fonts, missing assets, overflow, unsupported effects, or dimension mismatches. Never silently substitute or skip.

## References

- Read `references/config-schema.md` before creating or changing a batch specification.
- Read `references/flattened-recovery.md` whenever only a flattened finished image is available or typography must be inferred.
- Read `references/typography-and-qa.md` for text shaping, wrapping, visual QA, flat-image reconstruction, and animation checks.
- Read `references/bundled-fonts.md` before selecting, replacing, or redistributing bundled fonts.

## Completion criteria

- Every requested variant has every requested template.
- Every template uses its own measured coordinates and passes its own safe-area and alignment-group checks.
- Replaced regions contain no visible remnants of the old element.
- Flattened-only reconstruction reports zero changed pixels outside every approved erase mask.
- All elements remain inside intended safe areas without collisions; aligned groups meet their configured edge tolerance using rendered ink or group bounds.
- Typography, imagery, masks, colors, and effects match the current project's references.
- Mixed RTL/LTR content keeps logical character order while honoring the requested physical alignment, and grapheme-sensitive scripts contain no broken clusters at line boundaries.
- Static output dimensions and animated metadata match the specification.
- The report records input, output, chosen font sizes, line breaks, ink/group bounds, applied overrides, layout warnings, and animation metadata. QA grids cover every template and variant.
