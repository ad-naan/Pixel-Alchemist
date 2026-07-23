# Glass chrome, clean masters, and occlusion

Lessons from multi-language ad production where agents repeatedly retuned crop boxes instead of fixing the layer model.

## Contents

1. Decision order before any crop
2. When not to punch occlusion holes
3. Extracting glass capsules and pills
4. Difference plates vs rectangular stamps
5. Adaptive-width chrome with fixed height
6. Phone screens under transparent props
7. Stop criteria for mask iteration

## Decision order before any crop

1. Inventory whether each critical object is (a) a supplied RGBA asset, (b) baked into a clean background, (c) baked into a finished reference, or (d) only present under other pixels.
2. Write the intended z-order once. Example: background → warped screens → device frame/body → coins/shields/props → logo → adaptive chrome → headline.
3. Choose the material strategy:
   - supplied RGBA asset → place last, no crop tuning against underlayers
   - clean finished glass → extract one master plate
   - only baked under text → erase ink, keep plate, do not redraw glass
   - no clean pixels → report uncertainty; do not fake glass with solid gradients
4. Only after the model is fixed, measure coordinates.

If the user is already rejecting crop after crop, stop and restate which of the four source cases is true. Do not emit another polygon.

## When not to punch occlusion holes

Occlusion polygons on a replacement layer are valid when the foreground is fully opaque relative to the screen (hand, solid badge, thick device lip).

Do **not** punch holes under:

- translucent glass shields or capsules
- semi-transparent props where the underlayer should still read through
- assets that will be re-composited after the screen is placed

Prefer:

1. Leave the underlayer complete.
2. Composite the replacement screen.
3. Restore device frame/body.
4. Composite the transparent prop last.

Yellow or white bites beside a glass prop almost always mean the underlayer was cut before the glass cover.

## Extracting glass capsules and pills

### Choose one clean master

When three pills share the same style:

- Rank candidates by freedom from coins, hands, other chrome, and busy gradients.
- Use only the cleanest plate for all siblings.
- Never average three polluted crops.

### Crop with soft-edge padding

Include outer glow, drop shadow, and anti-aliased rim. Typical padding is 8–16 px beyond the hard silhouette on 1080-class canvases; measure from the blank-vs-finished difference rather than guessing.

### Erase only original label ink

When removing English or a blue dot:

- Mask glyph pixels and the dot glow tightly.
- Dilate slightly for AA.
- Do not draw a rectangle from endcap to endcap.
- Inpaint on the difference-from-blank field when a matching blank template exists.

A black bite on either endcap means the erase mask touched the glass rim.

## Difference plates vs rectangular stamps

Finished glass on a busy background cannot be pasted as RGB without carrying wrong scenery.

Preferred composite:

1. `plate_rgb = finished_crop`
2. `blank_rgb = matching_blank_crop` when available
3. `delta = plate_rgb - blank_rgb` stored as `delta + 128`
4. After mid-slice resize of the delta plate, apply `canvas_rgb += delta` only under the glass footprint

If only a true alpha cutout exists, use premultiplied alpha composite. Never paste a rectangular RGB crop that still contains coins or wall texture.

## Adaptive-width chrome with fixed height

Rules for multi-language pills:

- One font size for all pills in the same template.
- Height locked to the master plate.
- Width = text advance + fixed left chrome (dot/gap) + fixed right padding.
- 9-slice / mid-stretch: keep left and right endcaps pixel-intact; only stretch the middle strip.
- RTL variants reverse physical placement of the leading marker and text anchors; do not mirror the glass texture unless the art is designed to mirror.

QA:

- sibling font sizes equal
- no endcap distortion
- no rectangular dirty edge when over coins
- Arabic marker on the reading-start side

## Phone screens under transparent props

Master-layer pipeline still applies, but occlusion policy changes when props are glass:

1. Build the screen master with interior clip only (device glass bounds, AA radius matching the shell).
2. Do not remove translucent prop regions from the screen alpha if the prop will be composited later with its own RGBA.
3. After mapping the screen into a canvas, restore the solid device frame from the template.
4. Composite the supplied shield/coin/prop assets last.

If the prop is only baked into the template and no RGBA asset exists, extract a padded alpha master from the finished art once, then treat it as a supplied asset.

## Stop criteria for mask iteration

Abort the crop/mask loop and change strategy when any of the following is true:

- three consecutive crops still leave hard edges on glass
- expanding a mask starts erasing coins, hands, or device chrome
- a transparent prop shows double edges after "restore"
- a procedurally redrawn glass plate looks like a solid button under review
- different templates keep rediscovering the same occlusion hole

Escalation order:

1. Obtain or extract a clean RGBA master.
2. Fix z-order / difference composite.
3. Only then refine coordinates by a few pixels.

## Minimum QA crops

Before full-batch delivery, inspect 100–200% crops of:

- every glass endcap
- glass over coins/props
- glass/shield junction with phone screens
- RTL leading marker and trailing padding
- longest localized label at adaptive width


## Foreground avoidance mask precision

When removing or avoiding foreground props:

- Derive the mask from the prop silhouette itself, not from a coarse placement rectangle.
- Threshold soft alpha (for example keep alpha >= 96) so the glow halo is not treated as solid body.
- Expand at most 1–3 px for antialiasing. Do not use large dilations (9–15 px) around glass props.
- Text-safety analyzers must keep a fine enough grid (roughly width/6, capped around 256) and mild morphology; a 96-wide grid plus MaxFilter(5) merges phones, shields, and coins into one oversized avoidance blob.
- Phone exclusion padding should stay near the measured body (about 1–2% of canvas), not 3–4%.
