---
name: pixel-alchemist
description: Batch inspect, recover, measure, remove, replace, transform, compress, and validate elements in arbitrary static images and animated GIFs. Use for bulk image production involving flattened-image recovery, precise masks, perspective screen or product replacement, reusable transparent master layers, multilingual typography, logos, buttons, QR/image assets, inpainting, layout adaptation, per-variant data, frame-accurate animation, delivery size budgets, or pixel-level visual QA.
---

# Pixel Alchemist

Build deterministic batches from arbitrary source images using project data, measured layouts, and reusable rendering primitives.

## Workflow

1. Inventory inputs with `scripts/inventory_assets.py`. Classify flat images, clean backgrounds, references, layered assets, fonts, spreadsheets, vectors, masks, and animations. Preserve the SHA-256 manifest and compare it again when the user supplies revised assets.
2. Choose the safest source strategy. Use clean or layered sources when available. When only a flattened finished image exists, run `scripts/analyze_flattened_text.py` with known copy, search regions, colors, and candidate fonts; preserve its ink masks, effect masks, font matches, coordinates, and ready-to-paste render specs. When the reference uses metallic, ivory, neon, translucent, or otherwise non-flat text, run `scripts/sample_text_material.py` on each distinct semantic role before recreating the effect.
3. Reconstruct flattened regions with `scripts/erase_text_mask.py`. Require `outside_mask_byte_identical: true`; inspect seams before redrawing. Without a clean source, treat pixels under the old glyphs as an estimate rather than claiming the unknowable original background was recovered exactly.
4. When clean and finished references both exist, measure their differences with `scripts/measure_reference_diff.py`. Generate annotated previews and convert observed ink bounds into padded safe boxes. Measure every template independently, mark fixed foreground artwork as obstacles, and visualize resolved safe regions. Only when supplied targets are proven crops or mappings of one transformed visual layer, build that imagery once with `scripts/build_layer_family.py`; keep template-specific copy and logos independent.
5. Extract batch data from the supplied workbook or JSON. Model each output as a generic `variant`; variants may represent languages, products, regions, dates, prices, channels, or any combination.
6. Define templates and ordered elements in JSON using `references/config-schema.md`. Keep coordinates, copy, assets, effects, and per-variant overrides out of renderer code. Put shared-edge and spacing constraints inside the template they govern; never use an alignment group to impose one coordinate across different templates.
7. Validate fonts and complex shaping with `scripts/check_text_runtime.py`. Reuse `assets/font-presets.json` when appropriate, but let project fonts override it.
8. Render with `scripts/render_batch.py`. Use built-in elements for normal work and a project hook for custom blend modes, coordinated motion, procedural graphics, or timeline behavior. Use the layer-family tool for reusable perspective-mapped RGBA imagery instead of rewriting that transform in each project hook.
9. Validate coverage, sizes, frames, durations, disposal, loops, safe-area containment, template-local alignment groups, rendered-ink collisions with both elements and fixed obstacles, unnecessary wrapping, semantic phrase integrity, short tail lines, compound-button centering, and minimum readable font sizes. Generate a QA grid for every template.
10. Inspect representative extremes: every template, smallest canvas, largest canvas, longest text, densest composition, mixed-direction text, Thai or another grapheme-sensitive script, transparent source, flattened-only source, and animated source.
11. Write results only to a new output directory. For incremental redraws, merge reports with `scripts/merge_render_reports.py` and require complete config coverage. Validate the complete render set before compression, compress final delivery with `scripts/compress_to_budget.py`, inspect its dimension/metadata report, and create a final hashed inventory.

## Non-negotiable rules

- Prefer reversible compositing from clean sources. Use explicit masks and inpainting only when clean pixels are unavailable.
- Change no pixel outside an approved flattened-image erase mask. Expand the mask to include antialiasing, stroke, shadow, glow, and compression halos before reconstruction.
- Treat exact font family and weight as candidate-matching results. Require known text plus candidate font files for strong identification; otherwise report estimates and confidence instead of inventing certainty.
- Treat effect names such as “gold,” “metallic,” or “warm white” as visual descriptions, not render specifications. Measure the actual foreground pixels, determine the observed gradient axis, and reproduce the simplest sampled curve. Do not invent a vertical highlight band when the reference is a subtle horizontal transition.
- Sample headline emphasis, feature titles, body copy, and icons separately. Apply gradients in local glyph or line coordinates, clipped to the antialiased ink mask; never stretch one global canvas gradient across unrelated lines or roles.
- Preserve intentional newlines before automatic wrapping. For copy intended to stay on one line, try every approved single-line font size before allowing wrapping. Never distort glyphs horizontally.
- Treat legal character boundaries as different from approved semantic boundaries. Keep configured phrases on one line, reject forbidden line starts or ends, and fail visibly on an unbalanced short tail when the template declares a threshold.
- A text box is not proof of free space. Declare fixed visual obstacles and a maximum approved `flow_box`; subtract only obstacles that cross the text's vertical band, then validate the final rendered ink against those obstacles.
- Keep text direction separate from physical placement. `direction` controls shaping and reading order; `physical_align` controls the visible left, center, or right edge of the element on the canvas.
- Wrap Thai and other combining-mark scripts by language-aware segments or grapheme clusters, never raw Unicode code points. Fail when the approved box and size range cannot hold valid lines.
- Keep fixed content fixed only when the current request identifies it as fixed.
- Apply corrections at the narrowest scope: base element, current template, then current variant's override for that template. Do not globally shrink or move unrelated templates or outputs.
- Require RAQM for Arabic and other bidirectional shaping. Never reverse Unicode strings manually.
- Treat icons, logos, QR codes, and product cutouts as generic image assets with default and variant-specific fallbacks.
- Center button labels and arrows as one measured compound unit. Record their separate and combined bounds; remove an arrow only when the template explicitly permits it.
- Perform perspective resampling on premultiplied alpha with supersampling. Preserve antialiased alpha and remove foreground occluders from the transparent layer instead of painting over them.
- Preserve GIF frame count, timing, disposal, transparency, and loop. Draw on every affected frame.
- Put exceptional behavior in `before_frame`, `draw_element`, or `after_frame` hooks instead of forking the generic renderer.
- Fail visibly on missing fonts, missing assets, overflow, unsupported effects, or dimension mismatches. Never silently substitute or skip.

## References

- Read `references/config-schema.md` before creating or changing a batch specification.
- Read `references/flattened-recovery.md` whenever only a flattened finished image is available or typography must be inferred.
- Read `references/typography-and-qa.md` for text shaping, wrapping, visual QA, flat-image reconstruction, and animation checks.
- Read `references/layer-families-and-delivery.md` for perspective screen/product replacement, premultiplied alpha, occlusion masks, asset manifests, incremental redraws, compression budgets, and semantic or compound-button QA.
- Read `references/bundled-fonts.md` before selecting, replacing, or redistributing bundled fonts.

## Completion criteria

- Every requested variant has every requested template.
- Every template uses its own measured coordinates and passes its own safe-area and alignment-group checks.
- Replaced regions contain no visible remnants of the old element.
- Flattened-only reconstruction reports zero changed pixels outside every approved erase mask.
- All elements remain inside intended safe areas without collisions with other rendered elements or declared fixed obstacles; aligned groups meet their configured edge tolerance using rendered ink or group bounds.
- Line-locked copy stays on one line whenever it fits at or above its approved single-line minimum size; intentional newlines remain unchanged.
- Typography, imagery, masks, colors, and effects match the current project's references.
- Styled text uses the measured axis, sampled color stops, role-specific treatment, and local coordinate system recorded in the report; 100% crops show no visible banding or unjustified contrast.
- Mixed RTL/LTR content keeps logical character order while honoring the requested physical alignment, and grapheme-sensitive scripts contain no broken clusters at line boundaries.
- Static output dimensions and animated metadata match the specification.
- Reusable master layers have clean antialiased edges, correct occlusion holes, and proven mappings for every derived target.
- Every delivery file is strictly below its declared byte budget; GIF frame count, durations, disposal, and loop remain unchanged after compression.
- The report records input, output, chosen font sizes, line breaks, ink/group bounds, applied overrides, layout warnings, and animation metadata. QA grids cover every template and variant.
