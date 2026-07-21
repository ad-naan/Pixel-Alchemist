# Layer families and delivery

Use this workflow when one transformed visual layer, such as a phone screen, monitor UI, product label, or foreground cutout, is shared by several canvases. Keep text, logos, and other template-specific layout in the normal batch renderer unless the supplied artwork proves they use the same geometric mapping.

## Contents

1. Master-layer decision
2. Layer-family configuration
3. Alpha and occlusion rules
4. Asset version checks
5. Incremental render reports
6. Delivery compression
7. Typography and compound-button QA

## Master-layer decision

Use one maximum-resolution master layer only when all target artworks are crops, resizes, or perspective mappings of that layer. Confirm the relationship with matched reference points or a measured homography. Do not infer it from similar-looking layouts.

The intended pipeline is:

1. Map each variant source into the maximum-resolution master canvas.
2. Clip the result to the approved interior mask.
3. Remove foreground occluders from the layer alpha.
4. Save the reusable transparent master PNG.
5. Map that master into each proven target canvas.
6. Composite the mapped layer below the original frame, device shell, island/notch, badge, hand, or other foreground artwork.

Run `scripts/build_layer_family.py` for this pipeline. It performs perspective warps on premultiplied RGBA data, renders at a configurable supersampling factor, and downsamples before converting back to straight alpha. This prevents transparent RGB from bleeding dark or bright fringes into antialiased edges.

## Layer-family configuration

Store source and destination corners in clockwise order: top-left, top-right, bottom-right, bottom-left. A stage that changes canvas size must provide a 3x3 `matrix` or at least one explicit quad; an omitted source quad means the full source image, and an omitted destination quad means the full target canvas. Identity mapping is accepted only when source and target canvas sizes match.

```json
{
  "supersample": 3,
  "master": {
    "canvas": [2048, 1152],
    "source_quad": [[0, 0], [1170, 0], [1170, 2532], [0, 2532]],
    "destination_quad": [[1420, 180], [1850, 238], [1810, 1040], [1360, 970]],
    "clip_mask": "masks/master-screen-interior.png",
    "occlusion_polygons": [
      [[1540, 190], [1730, 210], [1715, 270], [1528, 250]],
      [[1670, 620], [1900, 650], [1870, 920], [1640, 885]]
    ],
    "output": "master-screen.png"
  },
  "targets": {
    "wide": {
      "canvas": [1500, 500],
      "source_quad": [[274, 112], [1774, 112], [1774, 612], [274, 612]],
      "destination_quad": [[0, 0], [1500, 0], [1500, 500], [0, 500]],
      "output": "wide-screen.png"
    },
    "square": {
      "canvas": [1080, 1080],
      "matrix": [[0.75, 0, -210], [0, 0.75, 95], [0, 0, 1]],
      "output": "square-screen.png"
    }
  },
  "variants": [
    {"id": "en", "source": "screens/en.png"},
    {"id": "ar", "source": "screens/ar.png"}
  ]
}
```

```powershell
python scripts\build_layer_family.py layer-family.json --output-dir work\layers
```

Variant records may override `master` or individual `targets` only when source geometry genuinely differs. Keep the common transform in the base stage.

## Alpha and occlusion rules

- Treat `clip_mask` white pixels as the layer interior to keep.
- Treat `occlusion_masks` white pixels as foreground regions to remove from layer alpha.
- Use `clip_polygon` for a simple measured interior and `occlusion_polygons` for simple foreground shapes.
- Prefer full-canvas antialiased masks for rounded device corners, hair, hands, glass, or irregular product silhouettes.
- Never threshold antialiased alpha to binary after a perspective warp.
- Inspect the master at 200–400% zoom, including every corner, device frame, notch/island, foreground badge, and bottom edge.
- Validate target canvases from the saved master layer, not by independently re-estimating the source perspective for each size.

`layer-family-report.json` records every matrix, output size, nonzero alpha count, and alpha bounding box. A nonempty alpha box is necessary but does not prove correct z-order; composite representative layers over the real backgrounds for visual QA.

## Asset version checks

Run the asset inventory before rendering. It now records file modification time and a SHA-256 digest by default.

```powershell
python scripts\inventory_assets.py sources --output work\assets-before.json
python scripts\inventory_assets.py sources --output work\assets-current.json `
  --baseline work\assets-before.json
```

Review `changes.added`, `changes.changed`, and `changes.removed`. When a supplied logo or background changes, invalidate only templates that depend on that asset. Do not recolor an older logo in code when a new official light or dark asset was supplied.

## Incremental render reports

Rendering selected templates produces a partial `render-report.json`. Merge that partial report into the last complete report instead of replacing the audit history:

```powershell
python scripts\merge_render_reports.py work\full-report.json work\partial-report.json `
  --output work\merged-report.json --config batch.json
```

Rows are replaced by `(variant, template)`. `--config` requires exact coverage of every configured variant/template pair and fails on missing, unexpected, or duplicate rows. A skipped update without metrics preserves existing metrics for that row.

After merging, run `validate_outputs.py` against the complete output directory and merged report.

## Delivery compression

Compress only after rendering and visual QA. Write to a new output directory:

```powershell
python scripts\compress_to_budget.py output delivery `
  --static-max-bytes 200000 --gif-max-bytes 1000000
```

The budget comparison is strict: every file must be smaller than its threshold. Files already below budget are copied byte-for-byte. Oversized PNG files first receive lossless PNG optimization; opaque images then fall back to the highest JPEG quality that fits, while alpha images use WebP. File extensions change when the codec changes and the report records the final path.

GIF compression tests color counts from highest to lowest and accepts a candidate only when frame count, every frame duration, disposal values, and loop count remain unchanged. It never drops hold frames. If no approved candidate fits, the command exits nonzero and records the failure rather than silently degrading metadata.

The compressor reopens every output and fails if its dimensions changed or its byte count is not strictly below budget. Review `compression-report.json` for codec, quality or palette size, dimensions, final byte count, output path, animation metadata, and failures. Validate consumer format requirements before allowing JPEG or WebP fallback, then create a final SHA-256 inventory of the delivery directory.

## Typography and compound-button QA

Use explicit semantic newlines for approved language-specific breaks. Add template-local QA rules when visual balance or phrase integrity matters:

```json
{
  "qa": {
    "elements": {
      "headline": {
        "min_last_line_ratio": 0.35,
        "preserve_terms": ["Product Suite"],
        "forbidden_line_starts": [",", ".", ":"],
        "forbidden_line_ends": ["&", "/"]
      },
      "action": {
        "max_content_center_offset": 3
      }
    }
  }
}
```

`preserve_terms` ignores whitespace while checking whether a phrase was split across rendered lines. Configure forbidden starts and ends per language and template; do not use one universal particle list.

Buttons center the rendered label and vector arrow as one compound unit. Their metrics include `text_box`, `arrow_box`, `content_box`, `group_box`, and `content_center_offset_x`. Use `arrow_side: left|right|start|end` when the arrow's physical or logical side must be explicit. Long labels may drop the arrow only when `drop_arrow_if_needed` permits it.
