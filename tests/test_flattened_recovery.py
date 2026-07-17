from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


SKILL_DIR = Path(__file__).resolve().parents[1]
ANALYZER = SKILL_DIR / "scripts" / "analyze_flattened_text.py"
ERASER = SKILL_DIR / "scripts" / "erase_text_mask.py"
FONT_DIR = SKILL_DIR / "assets" / "fonts" / "poppins"


@unittest.skipIf(importlib.util.find_spec("cv2") is None, "OpenCV is not installed")
class FlattenedRecoveryTest(unittest.TestCase):
    def test_font_measurement_and_mask_scoped_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            width, height = 600, 300
            x_gradient = np.linspace(20, 72, width, dtype=np.float32)
            y_gradient = np.linspace(0, 24, height, dtype=np.float32)[:, None]
            clean_array = np.zeros((height, width, 3), dtype=np.uint8)
            clean_array[:, :, 0] = np.clip(x_gradient + y_gradient, 0, 255)
            clean_array[:, :, 1] = np.clip(x_gradient * 1.25 + y_gradient, 0, 255)
            clean_array[:, :, 2] = np.clip(x_gradient * 1.8 + y_gradient, 0, 255)
            clean = Image.fromarray(clean_array, "RGB")
            clean_path = root / "clean.png"
            clean.save(clean_path)

            finished = clean.copy()
            font = ImageFont.truetype(str(FONT_DIR / "Poppins-Bold.ttf"), 52)
            ImageDraw.Draw(finished).text((62, 104), "Pixel detail", font=font, fill="#FFFFFF")
            finished_path = root / "finished.png"
            finished.save(finished_path)

            spec = {
                "erase_expand": 4,
                "safe_padding": 5,
                "font_candidates": [
                    {"path": str(FONT_DIR / "Poppins-Regular.ttf"), "family": "Poppins", "weight": "regular"},
                    {"path": str(FONT_DIR / "Poppins-Bold.ttf"), "family": "Poppins", "weight": "bold"},
                ],
                "regions": [
                    {
                        "id": "headline",
                        "search_box": [40, 80, 520, 100],
                        "text": "Pixel detail",
                        "lines": ["Pixel detail"],
                        "fill_colors": ["#FFFFFF"],
                        "color_tolerance": 70,
                        "min_font_size": 46,
                        "max_font_size": 58,
                    }
                ],
            }
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            analysis_dir = root / "analysis"
            subprocess.run([sys.executable, str(ANALYZER), str(finished_path), str(spec_path), "--output-dir", str(analysis_dir)], check=True)
            analysis = json.loads((analysis_dir / "analysis.json").read_text(encoding="utf-8"))
            measured = analysis["regions"][0]
            best = measured["font_matches"][0]
            self.assertEqual(best["weight"], "bold")
            self.assertLessEqual(abs(best["font_size"] - 52), 2)
            self.assertEqual(measured["fill_color"], "#FFFFFF")

            output_path = root / "cleaned.png"
            report_path = root / "erase-report.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ERASER),
                    str(finished_path),
                    str(analysis_dir / "combined-erase-mask.png"),
                    "--output",
                    str(output_path),
                    "--report",
                    str(report_path),
                    "--ground-truth",
                    str(clean_path),
                ],
                check=True,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["outside_mask_byte_identical"])
            self.assertEqual(report["changed_outside_mask_pixels"], 0)
            self.assertLess(report["ground_truth_mae_inside_mask"], 3.0)


if __name__ == "__main__":
    unittest.main()
