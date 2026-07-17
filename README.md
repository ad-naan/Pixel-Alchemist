# Pixel Alchemist · 像素炼金术师

Turn a folder of source images into a reproducible batch of edited static images and frame-accurate GIFs.

把一批原始图片变成可重复执行、可检查、可扩展的静态图与逐帧 GIF 成品。

Pixel Alchemist is a Codex skill and Python toolkit for measuring, removing, replacing, and drawing image elements at scale. It handles text, images, logos, icons, product cutouts, prices, dates, buttons, shapes, masks, multilingual layouts, and custom animation.

Pixel Alchemist 是一个用于批量测量、擦除、替换和绘制图片元素的 Codex Skill 与 Python 工具集。它可以处理文字、图片、标志、图标、商品、价格、日期、按钮、形状、遮罩、多语种排版与自定义动画。

![Pixel Alchemist English demo](examples/demo/output-en.png)

The demo starts from a generated text-free background and renders English and Arabic variants through the same JSON specification. Source, configuration, outputs, and render report are available in [`examples/demo`](examples/demo).

演示从一张无文字背景开始，通过同一份 JSON 配置绘制英文和阿拉伯语版本。背景、配置、成品和绘制报告均位于 [`examples/demo`](examples/demo)。

## Highlights · 核心能力

- Measure changed regions between clean backgrounds and finished references, with annotated coordinate previews.
- Batch by arbitrary variants: language, product, market, date, price, channel, or any combination.
- Fit multilingual text with explicit semantic line breaks, font fallback, stroke, shadow, and RTL shaping.
- Replace images with variant-aware fallbacks, `contain`/`cover`/`stretch`, opacity, and rotation.
- Draw buttons, rectangles, ellipses, polygons, lines, and measured icon-text groups.
- Remove flattened elements with solid fill, blur, masks, or OpenCV inpainting.
- Preserve GIF frame count, per-frame timing, disposal, transparency, and loop.
- Extend complex projects through frame hooks without forking the generic renderer.
- Validate output coverage, dimensions, fonts, and animation metadata.

## Repository layout · 目录结构

```text
pixel-alchemist/
├── SKILL.md
├── README.md
├── requirements.txt
├── agents/openai.yaml
├── scripts/
│   ├── inventory_assets.py
│   ├── measure_reference_diff.py
│   ├── check_text_runtime.py
│   ├── render_batch.py
│   └── validate_outputs.py
├── references/
│   ├── config-schema.md
│   ├── typography-and-qa.md
│   └── bundled-fonts.md
└── assets/
    ├── font-presets.json
    └── fonts/
```

## Install as a Codex skill · 安装为 Codex Skill

Clone or copy the folder into your personal skills directory:

```powershell
git clone https://github.com/ad-naan/Pixel-Alchemist.git "$env:USERPROFILE\.codex\skills\pixel-alchemist"
```

Then invoke it in Codex:

```text
Use $pixel-alchemist to inspect these source images, measure every replaceable element,
and render all requested variants into a clean output directory.
```

## Python environment · Python 环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\check_text_runtime.py --config assets\font-presets.json
```

Arabic and other bidirectional text require Pillow with RAQM, FriBiDi, and HarfBuzz support. SVG rendering uses the precompiled `resvg` backend. Run the runtime checker before production. The renderer fails explicitly instead of silently producing broken shaping.

阿拉伯语及双向文字需要 Pillow 的 RAQM、FriBiDi 和 HarfBuzz 支持。正式绘制前必须运行环境检查；环境不完整时脚本会明确报错，不会跳过或生成错误连写。

## Quick workflow · 快速流程

1. Inventory the project:

   ```powershell
   python scripts\inventory_assets.py path\to\sources --output work\inventory.json
   ```

2. Measure finished artwork against clean backgrounds:

   ```powershell
   python scripts\measure_reference_diff.py path\to\clean path\to\finished `
     --output work\measurements.json --preview-dir work\previews
   ```

3. Create a batch JSON using [`references/config-schema.md`](references/config-schema.md).

4. Render selected variants:

   ```powershell
   python scripts\render_batch.py batch.json `
     --background-dir path\to\backgrounds `
     --output-dir output `
     --variants variant-a variant-b
   ```

5. Validate outputs:

   ```powershell
   python scripts\validate_outputs.py batch.json output
   ```

Every variant is written into its own folder and `render-report.json` records chosen font sizes, line breaks, element metrics, and animation metadata.

## Configuration model · 配置模型

A template describes canvas size, background, output name, and ordered elements. A variant supplies values, language, assets, background overrides, and narrow layout exceptions.

模板负责画布尺寸、背景、输出文件名和元素顺序；变体负责文字数据、语种、图片资产、背景覆盖与局部版式修正。因此同一套脚本既能处理多语种，也能处理不同商品、日期、价格、地区和渠道。

```json
{
  "font_preset": "@skill/assets/font-presets.json",
  "templates": {
    "square": {
      "canvas": [1080, 1080],
      "background": "square.png",
      "output": "square.png",
      "elements": {
        "headline": {
          "type": "text",
          "value_key": "headline",
          "box": [80, 120, 920, 180],
          "max_font_size": 72,
          "min_font_size": 34,
          "max_lines": 2,
          "weight": "bold",
          "align": "center",
          "color": "#FFFFFF"
        }
      }
    }
  },
  "variants": [
    {"id": "variant-a", "language": "en", "values": {"headline": "A new headline"}},
    {"id": "variant-b", "language": "es", "values": {"headline": "Un nuevo titular"}}
  ]
}
```

## Complex scenes · 复杂场景

Use built-in elements for deterministic layout. For OCR-assisted masks, advanced retouching, clipping paths, perspective transforms, mesh warps, generated QR/barcodes, blend modes, or coordinated animation, pass a small project hook:

```python
def before_frame(canvas, context):
    pass

def draw_element(canvas, role, spec, context):
    if spec["type"] != "custom_effect":
        return None
    # Draw the project-specific effect and return audit metrics.
    return {"handled": True, "frame": context["frame_index"]}

def after_frame(canvas, context):
    pass
```

```powershell
python scripts\render_batch.py batch.json --background-dir backgrounds `
  --output-dir output --hook project_hook.py
```

## Test · 测试

```powershell
python -m unittest tests\test_smoke.py
```

The smoke test covers arbitrary variants, element removal, shapes, image assets, fitted text, output validation, and strict GIF metadata preservation.

## Fonts and licensing · 字体与授权

The repository includes common multilingual fonts only when their redistribution notices are bundled with the files. See [`references/bundled-fonts.md`](references/bundled-fonts.md).

Fonts whose files cannot be redistributed are not committed. The font reference links users to official download sources and shows how to configure local paths. Third-party fonts keep their own licenses. The Python source code also needs a repository license chosen by the repository owner before public release.

仓库只包含附有再分发许可文本的常用字体；不能直接分发的字体不上传，并在字体说明中引导用户从官方来源自行下载和配置。代码仓库采用何种开源许可证应由仓库所有者决定。
