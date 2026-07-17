# Typography, reconstruction, and QA

## Source reconstruction

- Prefer clean backgrounds, layered source files, vector originals, and separate foreground assets.
- With only a flattened image, create a precise mask around the old element. Use solid fill only on truly flat regions; use blur for deliberately defocused areas; use inpainting for continuous texture; use a hook or external retouching workflow for reflections, repeated geometry, faces, hands, or critical product detail.
- Expand a text mask enough to include antialiasing, shadows, glows, outlines, and compression halos. Feather only when the replacement method benefits from a soft boundary.
- Inspect the reconstructed region before drawing the new element.

## Font and text fitting

- Use project-supplied fonts first. Validate actual glyph coverage rather than trusting a family name.
- Treat explicit `\n` as immutable semantic breaks.
- Wrap space-delimited writing systems at words. For CJK or scripts without reliable spaces, use character wrapping only when no language-aware segmenter is available.
- Avoid orphaned final lines. Rebalance line breaks, widen the safe box, or reduce size within the approved range.
- Use element/template/variant overrides for genuine outliers. Do not solve one collision by shrinking every output.
- Include stroke width in fit measurements. Account for shadows and glows in safe-area padding.

## Bidirectional and complex scripts

- Require Pillow RAQM for Arabic and other bidirectional production output.
- Use logical Unicode text with the appropriate direction and language; never reverse strings manually.
- Inspect punctuation, mixed Latin fragments, numeric dates, combining marks, and line order at 100% zoom.
- Validate Thai, Indic, Arabic, and Southeast Asian shaping with the actual supplied font files.

## Images, icons, and generated codes

- Reuse supplied SVG/PNG/WebP assets whenever possible.
- Treat logos, icons, product cutouts, QR codes, barcodes, badges, and decorative marks as `image` elements or hook-generated assets.
- Use `contain` when the full asset must remain visible, `cover` when the box must be filled, and `stretch` only for assets designed to deform.
- Anchor image-and-text groups as one measured unit when their relative spacing must remain stable.

## Animation

- Inspect frame count, per-frame duration, loop, disposal, transparency, and partial-frame behavior before editing.
- Render on every affected frame. Use the hook frame index/count for timeline-dependent movement or effects.
- Preserve hold frames even when adjacent frames are visually identical. The bundled strict GIF writer prevents automatic frame coalescing.
- Compare the complete animation, not only the first frame.

## Visual QA matrix

Inspect at least:

1. Smallest and largest canvases.
2. Shortest and longest variable values.
3. Lightest and darkest backgrounds.
4. Every distinct writing system.
5. A variant using fallback assets and one using overrides.
6. Transparent output when requested.
7. First, middle, and last animation frames plus full playback.

Verify reconstruction seams, old-element remnants, safe boxes, collisions, font family and weight, line balance, image fit, z-order, opacity, rotation, masks, output dimensions, and animation metadata.
