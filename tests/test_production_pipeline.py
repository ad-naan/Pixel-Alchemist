from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence


ROOT = Path(__file__).resolve().parents[1]
LAYER_BUILDER = ROOT / "scripts" / "build_layer_family.py"
COMPRESSOR = ROOT / "scripts" / "compress_to_budget.py"
INVENTORY = ROOT / "scripts" / "inventory_assets.py"
MERGER = ROOT / "scripts" / "merge_render_reports.py"


def gif_metadata(path: Path) -> dict:
    with Image.open(path) as image:
        frames = list(ImageSequence.Iterator(image))
        return {
            "frames": len(frames),
            "durations_ms": [int(frame.info.get("duration", image.info.get("duration", 100))) for frame in frames],
            "disposals": [int(getattr(frame, "disposal_method", image.info.get("disposal", 0))) for frame in frames],
            "loop": int(image.info.get("loop", 0)),
        }


class ProductionPipelineTest(unittest.TestCase):
    def test_layer_family_preserves_clean_alpha_and_occlusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = Image.new("RGBA", (40, 40), (255, 0, 0, 0))
            array = np.asarray(source).copy()
            array[3:37, 3:37] = (255, 40, 20, 255)
            Image.fromarray(array, "RGBA").save(root / "screen.png")
            config = {
                "supersample": 3,
                "master": {
                    "canvas": [80, 60],
                    "destination_quad": [[10, 5], [70, 8], [68, 55], [12, 52]],
                    "clip_polygon": [[10, 5], [70, 8], [68, 55], [12, 52]],
                    "occlusion_polygons": [[[35, 20], [45, 20], [45, 30], [35, 30]]],
                    "output": "master.png",
                },
                "targets": {
                    "small": {
                        "canvas": [40, 30],
                        "source_quad": [[0, 0], [80, 0], [80, 60], [0, 60]],
                        "destination_quad": [[0, 0], [40, 0], [40, 30], [0, 30]],
                        "output": "small.png",
                    }
                },
                "variants": [{"id": "en", "source": "screen.png"}],
            }
            config_path = root / "layers.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            output = root / "output"
            subprocess.run([sys.executable, str(LAYER_BUILDER), str(config_path), "--output-dir", str(output)], check=True)

            with Image.open(output / "en" / "master.png") as rendered:
                rgba = np.asarray(rendered.convert("RGBA"))
            self.assertEqual(rgba.shape[:2], (60, 80))
            self.assertEqual(int(rgba[25, 40, 3]), 0)
            self.assertGreater(int(rgba[15, 25, 3]), 200)
            self.assertEqual(int(rgba[0, 0, 3]), 0)
            edge = rgba[(rgba[:, :, 3] > 0) & (rgba[:, :, 3] < 255)]
            self.assertGreater(len(edge), 0)
            self.assertGreater(float(edge[:, 0].mean()), 220)
            with Image.open(output / "en" / "small.png") as small:
                self.assertEqual(small.size, (40, 30))
            report = json.loads((output / "layer-family-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report[0]["master"]["size"], [80, 60])
            self.assertIn("small", report[0]["targets"])

    def test_compression_meets_strict_budgets_and_preserves_gif_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "input"
            source_dir.mkdir()
            rng = np.random.default_rng(7)
            Image.fromarray(rng.integers(0, 256, (256, 256, 3), dtype=np.uint8), "RGB").save(source_dir / "noise.png")

            durations = [30, 40, 50, 60, 70]
            frames = [Image.fromarray(rng.integers(0, 256, (80, 80, 3), dtype=np.uint8), "RGB") for _ in durations]
            frames[0].save(
                source_dir / "motion.gif",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                disposal=[2] * len(frames),
                loop=3,
                optimize=False,
            )
            expected_gif = gif_metadata(source_dir / "motion.gif")
            output = root / "output"
            subprocess.run(
                [
                    sys.executable,
                    str(COMPRESSOR),
                    str(source_dir),
                    str(output),
                    "--static-max-bytes",
                    "50000",
                    "--gif-max-bytes",
                    "30000",
                    "--min-quality",
                    "10",
                    "--gif-colors",
                    "256",
                    "128",
                    "64",
                    "32",
                    "16",
                ],
                check=True,
            )
            report = json.loads((output / "compression-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["failures"], [])
            rows = {Path(row["input"]).name: row for row in report["files"]}
            self.assertLess(rows["noise.png"]["output_bytes"], 50000)
            self.assertEqual(Path(rows["noise.png"]["output"]).suffix, ".jpg")
            self.assertLess(rows["motion.gif"]["output_bytes"], 30000)
            self.assertEqual(gif_metadata(Path(rows["motion.gif"]["output"])), expected_gif)

    def test_inventory_hash_diff_and_complete_report_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / "assets"
            assets.mkdir()
            (assets / "copy.txt").write_text("first", encoding="utf-8")
            Image.new("RGB", (12, 8), "#123456").save(assets / "background.png")
            baseline = root / "baseline.json"
            subprocess.run([sys.executable, str(INVENTORY), str(assets), "--output", str(baseline)], check=True)
            first = json.loads(baseline.read_text(encoding="utf-8"))
            self.assertTrue(all("sha256" in row for row in first["files"]))

            (assets / "copy.txt").write_text("second", encoding="utf-8")
            (assets / "new.txt").write_text("new", encoding="utf-8")
            (assets / "background.png").unlink()
            current = root / "current.json"
            subprocess.run(
                [sys.executable, str(INVENTORY), str(assets), "--output", str(current), "--baseline", str(baseline)],
                check=True,
            )
            changes = json.loads(current.read_text(encoding="utf-8"))["changes"]
            self.assertEqual(changes["added"], ["new.txt"])
            self.assertEqual(changes["changed"], ["copy.txt"])
            self.assertEqual(changes["removed"], ["background.png"])

            base_rows = [
                {"variant": "en", "template": "wide", "status": "rendered", "metrics": {"old": 1}},
                {"variant": "en", "template": "portrait", "status": "rendered", "metrics": {"keep": 1}},
            ]
            update_rows = [{"variant": "en", "template": "wide", "status": "rendered", "metrics": {"new": 1}}]
            base_report = root / "base-report.json"
            update_report = root / "update-report.json"
            merged_report = root / "merged-report.json"
            config = root / "batch.json"
            base_report.write_text(json.dumps(base_rows), encoding="utf-8")
            update_report.write_text(json.dumps(update_rows), encoding="utf-8")
            config.write_text(json.dumps({"templates": {"wide": {}, "portrait": {}}, "variants": [{"id": "en"}]}), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(MERGER),
                    str(base_report),
                    str(update_report),
                    "--output",
                    str(merged_report),
                    "--config",
                    str(config),
                ],
                check=True,
            )
            merged = json.loads(merged_report.read_text(encoding="utf-8"))
            self.assertEqual(merged[0]["metrics"], {"new": 1})
            self.assertEqual(merged[1]["metrics"], {"keep": 1})


if __name__ == "__main__":
    unittest.main()
