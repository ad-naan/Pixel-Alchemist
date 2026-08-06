# Reference-guided localization

Use this workflow when a finished design must be reproduced across languages, sizes, or placements without changing its imagery.

## Authority contract

Record four authorities before rendering:

1. **Copy authority**: workbook, CSV, JSON, or approved copy deck. Import exact strings; do not translate or editorialize.
2. **Visual authority**: exact finished reference for each template and size. Never infer one template from another when a matching reference exists.
3. **Font authority**: project font packages first, then explicitly approved script fallbacks. Record family, file, weight, role, and script coverage.
4. **Pixel authority**: immutable imagery, logos, people, products, architecture, and decoration outside the approved redraw mask.

If these authorities conflict, stop batch expansion and surface the conflict.

Normalize locale identities separately from filesystem aliases. For example, `CN`, `cn`, and `zh-CN` may map to Simplified Chinese, while a legacy project may use `zh` for Traditional Chinese. Never infer the latter mapping outside the current project's proven convention. Missing workbook locales are blocking source gaps unless the user explicitly requests a derivation; record the derivation source and method.

Classify visible text into explicit roles. Finished references may contain fixed event branding that is intentionally unchanged while workbook-driven title, subtitle, button, or award copy is localized. OCR is evidence for role discovery, not the copy authority.

## Proof gates

### Gate A: template calibration

For every template, render the reference language only and compare it with the exact finished reference. Measure:

- text ink bounds rather than nominal text boxes;
- font family, weight, size, tracking, line gap, baseline rhythm, and case;
- physical alignment and safe-region edges;
- logo order and fixed obstacles;
- decoration presence, count, length, thickness, gradient, anchor, and gap from ink.

Do not continue until every template has an accepted proof. A plausible composition is not a proof.

Font proof is per role, not per language. Record the actual resolved file, family, weight, shaping engine, size, and line gap for every text role. Compare this resolved table with both config and render report; a hidden system fallback in one small-copy role fails the proof.

### Gate B: complex-script sentinels

Render at least Arabic/RTL plus the grapheme-sensitive or widest scripts in the batch. Verify shaping, bidi order, font coverage, punctuation, numerals, semantic line breaks, minimum readable size, and collisions. Keep logical direction separate from physical placement.

### Gate C: batch expansion

Render all remaining variants only after Gates A and B pass. When a correction is script-specific, rerender only the affected variant/template pair, then validate the complete set again.

## Line-breaking contract

- Preserve author-provided newlines unless the approved target layout explicitly requires adaptation.
- Protect brand names, acronyms, dates, and configured phrases from internal breaks.
- Prefer semantic lines over equal visual widths.
- Do not force three lines merely because the reference language uses three lines.
- Reject orphaned short tails, forbidden line starts/ends, broken grapheme clusters, and line-height compression that causes visual crowding.

## Decoration contract

Decorative rules are not generic styling. Store them per template. Draw no rule when the exact reference has none. Never classify window mullions, horizon lines, table edges, or other background structures as decoration. Anchor rules to resolved text ink only after layout; enforce a positive measured gap so a rule cannot cross glyphs.

## Review surfaces

Create both:

- a per-template grid across all variants to reveal font and alignment drift;
- a per-variant overview across all templates to reveal inconsistent hierarchy and placement.

Inspect 100% crops for Arabic joins, Thai/Vietnamese marks, CJK punctuation, text remnants, metallic gradients, and decoration gaps. Overview sheets complement, but never replace, full-resolution inspection.

## Flattened sibling-donor recovery

When several flattened finals share the same photography/template but place different text in the same region, inventory them as a donor family. Register and align candidate siblings, select pixels that are clean under the target mask, then composite only those pixels into the target. A donor is acceptable only when outside-mask pixels remain byte-identical and every mask seam is reviewed at 100%. If donor texture differs, report it as a seam issue; do not hide it by regenerating the whole image.

## Runtime reconciliation gate

Treat hook overrides and renderer fallbacks as executable sources of truth that can diverge from configuration. Before delivery, require a resolved runtime report and fail on any validation error, missing metric, stale path, role without a font record, or difference between configured and actual font/effect choices. Dimension-and-hash inventories are useful but are not visual QA.
