from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence


SKILL_DIR = Path(__file__).resolve().parents[1]
RENDERER = SKILL_DIR / "scripts" / "render_batch.py"
VALIDATOR = SKILL_DIR / "scripts" / "validate_outputs.py"
VISUALIZER = SKILL_DIR / "scripts" / "visualize_layout.py"


class PixelAlchemistSmokeTest(unittest.TestCase):
    def test_static_variants_and_strict_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backgrounds = root / "backgrounds"
            backgrounds.mkdir()

            static = Image.new("RGB", (320, 180), "#173354")
            ImageDraw.Draw(static).text((18, 18), "OLD", fill="white")
            static.save(backgrounds / "static.png")

            symbol = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
            ImageDraw.Draw(symbol).ellipse((2, 2, 38, 38), fill="#FFAA22")
            symbol.save(root / "symbol.png")

            frames = []
            durations = [60, 90, 120]
            for index in range(3):
                frame = Image.new("RGB", (160, 80), "#101B36")
                ImageDraw.Draw(frame).ellipse((10 + index * 35, 42, 34 + index * 35, 66), fill="#49D2C8")
                frames.append(frame)
            frames[0].save(
                backgrounds / "motion.gif",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=2,
                disposal=1,
                optimize=False,
            )

            config = {
                "font_preset": "@skill/assets/font-presets.json",
                "assets": {"default": {"symbol": "symbol.png"}},
                "templates": {
                    "static": {
                        "canvas": [320, 180],
                        "background": "static.png",
                        "output": "static.png",
                        "elements": {
                            "erase": {"type": "erase", "box": [12, 12, 70, 30], "method": "solid", "color": "#173354"},
                            "panel": {"type": "rect", "z": 10, "box": [12, 12, 296, 156], "color": "#07152ECC", "radius": 18},
                            "symbol": {"type": "image", "z": 20, "asset_key": "symbol", "box": [28, 36, 40, 40]},
                            "title": {"type": "text", "z": 30, "value_key": "title", "box": [82, 30, 204, 62], "max_font_size": 28, "min_font_size": 16, "max_lines": 2, "weight": "bold", "align": "left", "color": "#FFFFFF"},
                        },
                    },
                    "motion": {
                        "canvas": [160, 80],
                        "background": "motion.gif",
                        "output": "motion.gif",
                        "animation": {"frames": 3, "durations_ms": durations, "loop": 2},
                        "elements": {
                            "caption": {"type": "text", "value_key": "caption", "box": [4, 4, 152, 28], "max_font_size": 16, "min_font_size": 10, "max_lines": 1, "weight": "bold", "align": "center", "color": "#FFFFFF"}
                        },
                    },
                },
                "variants": [
                    {"id": "first", "language": "en", "values": {"title": "First variant", "caption": "Frame test"}},
                    {"id": "second", "language": "en", "values": {"title": "Second variant", "caption": "Frame test"}},
                ],
            }
            config_path = root / "batch.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            output = root / "output"

            subprocess.run(
                [sys.executable, str(RENDERER), str(config_path), "--background-dir", str(backgrounds), "--output-dir", str(output), "--force"],
                check=True,
            )
            safe_zone_preview = root / "safe-zones.png"
            subprocess.run(
                [
                    sys.executable,
                    str(VISUALIZER),
                    str(config_path),
                    "--background-dir",
                    str(backgrounds),
                    "--template",
                    "static",
                    "--variant",
                    "first",
                    "--image",
                    str(output / "first" / "static.png"),
                    "--roles",
                    "title",
                    "--output",
                    str(safe_zone_preview),
                ],
                check=True,
            )
            subprocess.run([sys.executable, str(VALIDATOR), str(config_path), str(output)], check=True)

            safe_zone_report = json.loads(safe_zone_preview.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(safe_zone_report["safe_boxes"], [{"role": "title", "type": "text", "box": [82, 30, 204, 62]}])

            with Image.open(output / "first" / "motion.gif") as rendered:
                self.assertEqual(rendered.n_frames, 3)
                self.assertEqual(rendered.info.get("loop"), 2)
                actual_durations = [frame.info.get("duration") for frame in ImageSequence.Iterator(rendered)]
                self.assertEqual(actual_durations, durations)


if __name__ == "__main__":
    unittest.main()
