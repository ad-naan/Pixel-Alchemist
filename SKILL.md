---
name: pixel-alchemist
description: Batch inspect, recover, measure, remove, replace, transform, compress, and validate elements in arbitrary static images and animated GIFs. Use for bulk image production involving flattened-image recovery, reference-driven localization, precise masks, perspective screen or product replacement, reusable transparent master layers, multilingual typography, logos, buttons, QR/image assets, inpainting, layout adaptation, per-variant data, frame-accurate animation, delivery size budgets, pixel-level visual QA, glass/frosted chrome extraction, transparent prop z-order over phone screens, or adaptive-width capsule reuse.
---

# Pixel Alchemist

Build deterministic batches from arbitrary source images using project data, measured layouts, and reusable rendering primitives.

## Workflow

1. Inventory inputs with `scripts/inventory_assets.py`. Classify flat images, clean backgrounds, references, layered assets, fonts, spreadsheets, vectors, masks, and animations. Preserve the SHA-256 manifest and compare it again when the user supplies revised assets.
2. Choose the safest source strategy. Use clean or layered sources when available. When only a flattened finished image exists, run `scripts/analyze_flattened_text.py` with known copy, search regions, colors, and candidate fonts; preserve its ink masks, effect masks, font matches, coordinates, and ready-to-paste render specs. When the reference uses metallic, ivory, neon, translucent, or otherwise non-flat text, run `scripts/sample_text_material.py` on each distinct semantic role before recreating the effect.
2b. Before any crop or mask loop, lock the layer model. Name every stack in z-order (background, replacement screens, device shells, translucent chrome, coins/shields/props, copy). Prefer covering transparent foreground props over punching holes through underlayers. If a supplied RGBA asset exists for a prop, place that asset last; never invent polygon restores for glass.
3. Reconstruct flattened regions with `scripts/erase_text_mask.py`. Prefer, in order: a clean/layered source; an aligned clean sibling from the same template family composited only inside the erase mask; deterministic local reconstruction; then AI inpainting composited only inside the mask. Require `outside_mask_byte_identical: true`, zero changed pixels outside the mask, and reviewed 100% seam crops. Never accept a full-image AI rewrite as text removal. Without a clean source, treat pixels under the old glyphs as an estimate rather than claiming the unknowable original background was recovered exactly.
3b. For glass capsules, pills, frosted panels, or other translucent chrome: never redraw with solid gradients or procedural glass buttons when a finished reference exists. Extract one clean master plate, erase only the original label/dot ink, keep soft-edge padding, and composite as a difference plate or true alpha—not as a rectangular RGB stamp. When the same chrome repeats, pick the cleanest instance (no coin/hand/prop collision) and 9-slice only the middle for adaptive width; keep height and font size shared across siblings.
4. When clean and finished references both exist, measure their differences with `scripts/measure_reference_diff.py`. Generate annotated previews and convert observed ink bounds into padded safe boxes. Measure every template independently, mark fixed foreground artwork as obstacles, and visualize resolved safe regions. Only when supplied targets are proven crops or mappings of one transformed visual layer, build that imagery once with `scripts/build_layer_family.py`; keep template-specific copy and logos independent.
5. Extract batch data from the supplied workbook or JSON. Model each output as a generic `variant`; variants may represent languages, products, regions, dates, prices, channels, or any combination.
5b. Declare source authority before editing: identify the copy source, the visual reference for each template, the approved font source for each script and role, and which pixels must remain immutable. Canonicalize locale aliases in config while retaining original folder names in the manifest. When a workbook supplies final copy, preserve its strings exactly in the batch data; do not translate, normalize punctuation, or rewrite it during rendering. Treat an absent requested locale as a source gap: stop unless the user explicitly authorizes derived copy, then label that value as derived in the report.
6. Define templates and ordered elements in JSON using `references/config-schema.md`. Keep coordinates, copy, assets, effects, and per-variant overrides out of renderer code. Put shared-edge and spacing constraints inside the template they govern; never use an alignment group to impose one coordinate across different templates.
7. Validate fonts and complex shaping with `scripts/check_text_runtime.py`. Search `assets/font-catalog.json` for bundled families, weights, scripts, hashes, and license files; regenerate it with `scripts/index_font_assets.py` after adding fonts. Reuse `assets/font-presets.json` when appropriate, but let project fonts override it.
7b. For reference-driven localization, calibrate one reference-language proof for every template before rendering all variants. Measure rendered ink, baselines, line gaps, fixed obstacles, decoration count, decoration geometry, and physical alignment from the exact matching finished reference. Read `references/reference-guided-localization.md` and pass its proof gates before batch expansion.
8. Render with `scripts/render_batch.py`. Use built-in elements for normal work and a project hook for custom blend modes, coordinated motion, procedural graphics, or timeline behavior. Use the layer-family tool for reusable perspective-mapped RGBA imagery instead of rewriting that transform in each project hook. After the reference-language proof passes, render complex-script sentinels before the complete batch.
9. Validate coverage, sizes, frames, durations, disposal, loops, safe-area containment, template-local alignment groups, rendered-ink collisions with both elements and fixed obstacles, unnecessary wrapping, semantic phrase integrity, short tail lines, compound-button centering, and minimum readable font sizes. Generate a QA grid for every template.
10. Inspect representative extremes: every template, smallest canvas, largest canvas, longest text, densest composition, mixed-direction text, Thai or another grapheme-sensitive script, transparent source, flattened-only source, and animated source.
10b. Build both QA views: one sheet per template across variants and one delivery overview grouped by variant across templates. Use `scripts/build_delivery_overview.py` for the latter. Never accept a batch from filenames and dimensions alone.
11. Write results only to a new output directory. For incremental redraws, merge reports with `scripts/merge_render_reports.py` and require complete config coverage. Reconcile the base config, project hook, resolved runtime spec, render report, and validation report; the resolved report is the authority for what was actually drawn. Validate the complete render set before compression, compress final delivery with `scripts/compress_to_budget.py`, inspect its dimension/metadata report, and create a final hashed inventory. A non-empty error list, missing metric, missing report, stale report path, or configured font that differs from the resolved font blocks delivery.

## Non-negotiable rules

- Prefer reversible compositing from clean sources. Use explicit masks and inpainting only when clean pixels are unavailable.
- Diagnose layer order and material strategy before tuning crop rectangles. Endless mask expansion is a symptom of the wrong model.
- Do not procedurally recreate glassmorphism, frosted glass, metal rims, or other non-flat chrome when the finished art already contains it. Sample or extract; do not invent.
- Do not extract repeated chrome from polluted positions (props, coins, hands, overlapping text). One clean master plate must drive every sibling.
- Crop soft materials with glow/shadow padding outside the hard silhouette; never clip to the opaque core.
- When cleaning labels off glass plates, mask only glyph/dot ink. Never flood-fill endcaps or rims with a broad rectangle inpaint.
- Composite translucent plates with difference-from-blank or true alpha. Pasting a rectangular RGB crop will reintroduce wrong background and square dirty edges.
- When a transparent glass prop must sit above a replacement screen, leave the underlayer whole and cover with the prop. Punching an occlusion hole under translucent glass creates yellow/white bites.
- If a baked-in translucent prop will be replaced by a supplied RGBA asset, erase or inpaint the baked instance first; never stack two glass copies.
- Adaptive chrome width: fixed height, shared sibling font size, mid-slice stretch only. Do not shrink endcap glass or vary font size across one visual set unless the brief demands it.
- Change no pixel outside an approved flattened-image erase mask. Expand the mask to include antialiasing, stroke, shadow, glow, and compression halos before reconstruction.
- Treat exact font family and weight as candidate-matching results. Require known text plus candidate font files for strong identification; otherwise report estimates and confidence instead of inventing certainty.
- Route fonts by script and role, not only by locale. Validate a real rendered sample for Arabic, Thai, Vietnamese, CJK, and mixed Latin/numeral content before full production. Do not silently fall back to a system font.
- Preflight and report every `(variant, template, text role)` tuple. A correct Arabic headline font does not prove that an Arabic subtitle, award label, button, or legal line used the same approved family.
- Treat effect names such as “gold,” “metallic,” or “warm white” as visual descriptions, not render specifications. Measure the actual foreground pixels, determine the observed gradient axis, and reproduce the simplest sampled curve. Do not invent a vertical highlight band when the reference is a subtle horizontal transition.
- Sample headline emphasis, feature titles, body copy, and icons separately. Apply gradients in local glyph or line coordinates, clipped to the antialiased ink mask; never stretch one global canvas gradient across unrelated lines or roles.
- Preserve intentional newlines before automatic wrapping. For copy intended to stay on one line, try every approved single-line font size before allowing wrapping. Never distort glyphs horizontally.
- Keep protected tokens such as product names, event marks, and acronyms indivisible. Never split a configured token such as `Adnify` merely to satisfy a line count.
- Treat legal character boundaries as different from approved semantic boundaries. Keep configured phrases on one line, reject forbidden line starts or ends, and fail visibly on an unbalanced short tail when the template declares a threshold.
- A text box is not proof of free space. Declare fixed visual obstacles and a maximum approved `flow_box`; subtract only obstacles that cross the text's vertical band, then validate the final rendered ink against those obstacles.
- Keep text direction separate from physical placement. `direction` controls shaping and reading order; `physical_align` controls the visible left, center, or right edge of the element on the canvas.
- Treat decorative rules as template-specific measured elements. Draw none unless the exact matching finished reference contains them. Record count, length, thickness, gradient, anchor, and minimum gap from rendered ink; background architecture is not evidence of a decorative rule.
- Wrap Thai and other combining-mark scripts by language-aware segments or grapheme clusters, never raw Unicode code points. Fail when the approved box and size range cannot hold valid lines.
- Keep fixed content fixed only when the current request identifies it as fixed.
- Apply corrections at the narrowest scope: base element, current template, then current variant's override for that template. Do not globally shrink or move unrelated templates or outputs.
- Scope user layout intent to the named role, template, and variant. A request for a three-line main title must not set every subtitle, button, or award label to three lines.
- Prefer local redraw patches composited over immutable source pixels. Do not regenerate or alter photography, logos, products, people, architecture, or unrelated decoration unless the request explicitly authorizes it.
- Require RAQM for Arabic and other bidirectional shaping. Never reverse Unicode strings manually.
- Treat icons, logos, QR codes, and product cutouts as generic image assets with default and variant-specific fallbacks.
- Center button labels and arrows as one measured compound unit. Record their separate and combined bounds; remove an arrow only when the template explicitly permits it.
- Perform perspective resampling on premultiplied alpha with supersampling. Preserve antialiased alpha and remove foreground occluders from the transparent layer instead of painting over them.
- Preserve GIF frame count, timing, disposal, transparency, and loop. Draw on every affected frame.
- Store delivery limits as exact byte integers. Never guess whether `200KB` means 200,000 or 204,800 bytes; resolve the convention before compression and require every output to be strictly below the recorded value.
- Put exceptional behavior in `before_frame`, `draw_element`, or `after_frame` hooks instead of forking the generic renderer.
- Fail visibly on missing fonts, missing assets, overflow, unsupported effects, or dimension mismatches. Never silently substitute or skip.

## References

- Read `references/config-schema.md` before creating or changing a batch specification.
- Read `references/flattened-recovery.md` whenever only a flattened finished image is available or typography must be inferred.
- Read `references/typography-and-qa.md` for text shaping, wrapping, visual QA, flat-image reconstruction, and animation checks.
- Read `references/layer-families-and-delivery.md` for perspective screen/product replacement, premultiplied alpha, occlusion masks, asset manifests, incremental redraws, compression budgets, and semantic or compound-button QA.
- Read `references/glass-chrome-and-occlusion.md` when the job involves glass capsules/pills, frosted panels, shields/coins, transparent props over phone screens, or repeated UI chrome extracted from flattened finals.
- Read `references/bundled-fonts.md` before selecting, replacing, or redistributing bundled fonts.
- Read `references/reference-guided-localization.md` when adapting a finished design across languages, sizes, or channels while preserving its original visual system.

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
- Validation reports contain zero errors and no missing metrics; every text role records its actual font file/family/weight, and those values agree with the resolved runtime spec rather than a stale base config.
- Visual review classifies and clears at least: source remnants, wrong font family/weight, malformed shaping, hierarchy or line-gap mismatch, material mismatch, invented/misplaced decoration, logo-order drift, and reference mismatch.
- The reference-language proof passes for every template before batch expansion; Arabic/RTL and at least one grapheme-sensitive script pass sentinel review before the remaining variants render.
- Decorations match the exact reference template and remain outside glyph ink with the measured gap; templates without decoration contain none.
- Workbook-sourced copy in config and reports exactly matches the authoritative cells, including punctuation and intentional line breaks.
