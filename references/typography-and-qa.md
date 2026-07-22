# Typography, reconstruction, and QA

## Source reconstruction

- Prefer clean backgrounds, layered source files, vector originals, and separate foreground assets.
- With only a flattened image, create a precise mask around the old element. Use solid fill only on truly flat regions; use blur for deliberately defocused areas; use inpainting for continuous texture; use a hook or external retouching workflow for reflections, repeated geometry, faces, hands, or critical product detail.
- Expand a text mask enough to include antialiasing, shadows, glows, outlines, and compression halos. Feather only when the replacement method benefits from a soft boundary.
- Inspect the reconstructed region before drawing the new element.

### Flattened-only recovery

Use `analyze_flattened_text.py` when no clean background exists. Supply the narrowest reasonable `search_box`, the known original copy when available, fill/stroke/shadow colors, and candidate fonts. The script emits:

- exact observed ink and effect masks;
- glyph/effect bounding boxes and padded safe boxes;
- per-line boxes, alignment, fill/stroke colors, and stroke-width estimates;
- ranked font family, weight, and size matches;
- a renderer-compatible text element draft.

Font recognition is a candidate comparison, not universal font identification. Strong results require the correct text and the actual font among the candidates. OCR can provide copy and coarse boxes, but always refine its boxes with pixel masks before erasing.

Run `erase_text_mask.py` with the emitted erase mask. It tests Telea, Navier-Stokes, and polynomial surface reconstruction in `auto` mode, composites only masked pixels, and fails if any outside pixel changes. A missing clean source makes the hidden background unknowable; the guarantee is therefore byte-identical pixels outside the mask plus measured seam quality, not proof of the original covered pixels.

## Font and text fitting

- Use project-supplied fonts first. Validate actual glyph coverage rather than trusting a family name.
- Treat explicit `\n` as immutable semantic breaks.
- Classify copy as line-locked or wrap-allowed. For line-locked copy, test the whole string across the approved font range before considering any line break; do not accept a larger wrapped layout merely because it was encountered first.
- Wrap space-delimited writing systems at words. Use a language-aware segmenter for Thai when available; otherwise wrap at extended grapheme clusters rather than Unicode code points. Apply the same grapheme rule to combining-mark scripts.
- Never begin a rendered line with a detached combining mark, split a conjunct or emoji sequence, or reorder text to imitate RTL.
- Avoid orphaned final lines. Rebalance line breaks, widen the safe box, or reduce size within the approved range. Use template-local `min_last_line_ratio` when a short tail must fail automated QA.
- Use `preserve_terms` for phrases or brand constructions that must remain together, and language-specific `forbidden_line_starts` or `forbidden_line_ends` for particles and punctuation. Do not assume every grapheme-safe break is semantically acceptable.
- Measure and fit each template independently. The same semantic role may have unrelated portrait, landscape, square, banner, and animation coordinates.
- Use a base element, template-local alignment group, `layout_overrides[template][element]`, then `alignment_overrides[template][group]` for genuine outliers. Do not solve one collision by shrinking every template or output.
- Include stroke width in fit measurements. Account for shadows and glows in safe-area padding.
- Measure fixed foreground artwork separately from text boxes. Store it as obstacle geometry, give text a maximum approved flow region, and compute free segments from the actual vertical band instead of imposing one narrow width on all rows.

## Bidirectional and complex scripts

- Require Pillow RAQM for Arabic and other bidirectional production output.
- Use logical Unicode text with the appropriate direction and language; never reverse strings manually.
- Keep `direction` separate from `physical_align`. Direction controls shaping and bidi order; physical alignment controls the visible canvas edge. An RTL paragraph may intentionally be physically left-aligned.
- Inspect punctuation, mixed Latin fragments, numeric dates, combining marks, and line order at 100% zoom.
- Validate Thai, Indic, Arabic, and Southeast Asian shaping with the actual supplied font files.

## Images, icons, and generated codes

- Reuse supplied SVG/PNG/WebP assets whenever possible.
- Treat logos, icons, product cutouts, QR codes, barcodes, badges, and decorative marks as `image` elements or hook-generated assets.
- Use `contain` when the full asset must remain visible, `cover` when the box must be filled, and `stretch` only for assets designed to deform.
- Anchor image-and-text groups as one measured unit when their relative spacing must remain stable. Report the complete group bounds, icon bounds, text ink bounds, and actual gap.
- Treat a button label and arrow as one measured unit. Center the compound content rather than centering the label in the leftover area, and validate `content_center_offset_x` when visual centering is strict.

## Template-local layout constraints

- Put every alignment group inside the template it governs. A group never shares a coordinate with another template implicitly.
- Align members by rendered left edge, right edge, or centerline using either an `anchor_role` or an explicit `position`, never both.
- Put rendered alignment assertions under the `template.qa.alignment_groups` list; each assertion names `roles`, `edge`, `metric`, and `tolerance`. QA describes acceptance and never changes placement.
- Use `template.qa.spacing` for required vertical or horizontal gaps, `template.qa.non_overlap` for rendered-element collision pairs, `template.qa.obstacle_clearance` for fixed-background collisions, and `template.qa.elements` for safe-area, minimum-font, and unnecessary-wrap requirements.
- Apply variant exceptions only to the affected template. Record every applied element or alignment override in the render report.

## Animation

- Inspect frame count, per-frame duration, loop, disposal, transparency, and partial-frame behavior before editing.
- Render on every affected frame. Use the hook frame index/count for timeline-dependent movement or effects.
- Preserve hold frames even when adjacent frames are visually identical. The bundled strict GIF writer prevents automatic frame coalescing.
- Compare the complete animation, not only the first frame.

## Visual QA matrix

Inspect at least:

1. Every template as its own coordinate system, including smallest and largest canvases.
2. Shortest and longest variable values and the smallest selected font size.
3. Lightest and darkest backgrounds.
4. Every distinct writing system, including a mixed RTL/LTR string and a grapheme-sensitive long string.
5. A variant using fallback assets, one using an element override, and one using an alignment override.
6. Every `icon_text` logical side and physical group-alignment mode used in production.
7. Transparent output when requested.
8. First, middle, and last animation frames plus full playback.

Generate one labeled QA grid per template with all requested variants in a stable order. Add badges or a companion report for language, direction, selected font, selected size, line count, fallback use, and applied overrides. A grid is a review surface, not a substitute for automated checks.

Verify reconstruction seams, old-element remnants, actual ink bounds, compound group bounds, declared obstacle bounds, maximum flow boxes, resolved free segments, alignment tolerances, spacing, collisions, safe boxes, unnecessary wrapping, minimum readable size, font family and weight, measured font-match confidence, outside-mask changed-pixel count, line balance, image fit, z-order, opacity, rotation, masks, output dimensions, and animation metadata. Fail on detached Thai marks, malformed bidi order, missing fonts, unapproved fallback, overflow, misalignment, needless line breaks, or overlap.

For perspective-mapped master layers and final size-budget compression, follow `layer-families-and-delivery.md`; those checks supplement rather than replace the template QA matrix.
