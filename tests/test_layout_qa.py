from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL_DIR / "scripts" / "validate_outputs.py"
GRID_BUILDER = SKILL_DIR / "scripts" / "build_qa_grid.py"


class LayoutQaTest(unittest.TestCase):
    def make_project(self, root: Path) -> tuple[Path, Path, list[dict]]:
        output = root / "output"
        (output / "sample").mkdir(parents=True)
        Image.new("RGB", (240, 160), "#19345A").save(output / "sample" / "portrait.png")
        Image.new("RGB", (400, 120), "#19345A").save(output / "sample" / "landscape.png")
        config = {
            "templates": {
                "portrait": {
                    "canvas": [240, 160],
                    "background": "portrait.png",
                    "output": "portrait.png",
                    "elements": {
                        "title": {"type": "text", "box": [8, 8, 50, 22]},
                        "date": {"type": "text", "box": [8, 32, 50, 20]},
                        "portrait": {"type": "image", "box": [96, 0, 100, 150]},
                        "panel": {"type": "rect", "box": [0, 0, 80, 80]},
                    },
                    "obstacles": {"fixed_art": {"box": [145, 8, 24, 30], "padding": 2}},
                    "qa": {
                        "containment": True,
                        "alignment_groups": [{"roles": ["title", "date"], "edge": "left", "metric": "ink_box", "tolerance": 2}],
                        "spacing": [{"from": "title", "to": "date", "axis": "y", "min": 4}],
                        "non_overlap": [["title", "portrait"]],
                        "obstacle_clearance": [{"roles": ["title"], "obstacles": ["fixed_art"]}],
                        "elements": {
                            "title": {
                                "min_font_size": 20,
                                "min_font_scale": 0.5,
                                "max_height_density": 0.8,
                                "containment_tolerance": 0,
                                "forbid_unnecessary_wrap": True,
                            }
                        },
                    },
                },
                "landscape": {
                    "canvas": [400, 120],
                    "background": "landscape.png",
                    "output": "landscape.png",
                    "elements": {
                        "title": {"type": "text", "box": [198, 8, 90, 24]},
                        "date": {"type": "text", "box": [198, 42, 90, 20]},
                    },
                    "qa": {
                        "containment": True,
                        "alignment_groups": [{"roles": ["title", "date"], "edge": "left", "metric": "ink_box", "tolerance": 2}],
                        "spacing": [{"from": "title", "to": "date", "axis": "y", "min": 6}],
                    },
                },
            },
            "variants": [
                {
                    "id": "sample",
                    "language": "en",
                    "values": {},
                    "qa_overrides": {
                        "landscape": {
                            "spacing": [{"from": "title", "to": "date", "axis": "y", "min": 10}]
                        }
                    },
                }
            ],
        }
        config_path = root / "batch.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        report = [
            {
                "variant": "sample",
                "template": "portrait",
                "metrics": {
                    "title": {
                        "safe_box": [8, 8, 50, 22],
                        "ink_box": [10, 10, 40, 15],
                        "font_size": 24,
                        "max_font_size": 28,
                        "font_scale": 24 / 28,
                        "height_density": 15 / 22,
                        "lines": ["Title"],
                        "line_count": 1,
                        "single_line_possible": True,
                    },
                    "date": {"ink_box": [11, 34, 35, 12], "font_size": 20, "lines": ["Date"]},
                    "portrait": {"ink_box": [100, 0, 90, 150]},
                    "panel": {"ink_box": [0, 0, 80, 80]},
                },
            },
            {
                "variant": "sample",
                "template": "landscape",
                "metrics": {
                    "title": {"ink_box": [201, 10, 70, 18], "font_size": 26, "lines": ["Title"]},
                    "date": {"ink_box": [200, 44, 62, 14], "font_size": 20, "lines": ["Date"]},
                },
            },
        ]
        (output / "render-report.json").write_text(json.dumps(report), encoding="utf-8")
        return config_path, output, report

    def test_template_scoped_rules_pass_and_do_not_flag_undeclared_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config, output, _ = self.make_project(Path(temporary))
            completed = subprocess.run(
                [sys.executable, str(VALIDATOR), str(config), str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["checked"], 2)
            self.assertEqual(result["violations"], [])

    def test_all_explicit_layout_failures_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, output, report = self.make_project(root)
            title = report[0]["metrics"]["title"]
            title.update({
                "ink_box": [143, 10, 40, 22],
                "font_size": 12,
                "font_scale": 0.3,
                "height_density": 0.95,
                "lines": ["Long", "title"],
                "line_count": 2,
                "single_line_possible": True,
                "single_line_min_width": 48,
            })
            report[0]["metrics"]["date"]["ink_box"] = [16, 25, 35, 12]
            report[0]["metrics"]["portrait"]["ink_box"] = [150, 15, 20, 20]
            (output / "render-report.json").write_text(json.dumps(report), encoding="utf-8")
            validation_json = root / "validation.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    str(config),
                    str(output),
                    "--json-output",
                    str(validation_json),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            result = json.loads(validation_json.read_text(encoding="utf-8"))
            rules = {item["rule"] for item in result["violations"]}
            self.assertTrue(
                {
                    "alignment",
                    "spacing",
                    "non_overlap",
                    "obstacle_clearance",
                    "typography.min_font_size",
                    "typography.min_font_scale",
                    "typography.max_height_density",
                    "typography.unnecessary_wrap",
                    "containment",
                }.issubset(rules)
            )

    def test_missing_metrics_fail_visibly_and_qa_grid_is_built(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, output, _ = self.make_project(root)
            (output / "render-report.json").unlink()
            completed = subprocess.run(
                [sys.executable, str(VALIDATOR), str(config), str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            result = json.loads(completed.stdout)
            self.assertEqual({item["rule"] for item in result["violations"]}, {"missing_render_metrics"})

            qa_dir = root / "qa"
            subprocess.run(
                [
                    sys.executable,
                    str(GRID_BUILDER),
                    str(config),
                    str(output),
                    "--qa-dir",
                    str(qa_dir),
                    "--columns",
                    "1",
                    "--cell-width",
                    "240",
                    "--cell-height",
                    "180",
                ],
                check=True,
            )
            with Image.open(qa_dir / "portrait-qa-grid.png") as grid:
                self.assertEqual(grid.size, (240, 180))
            with Image.open(qa_dir / "landscape-qa-grid.png") as grid:
                self.assertEqual(grid.size, (240, 180))
            manifest = json.loads((qa_dir / "qa-grid-report.json").read_text(encoding="utf-8"))
            self.assertEqual({item["template"] for item in manifest}, {"portrait", "landscape"})


if __name__ == "__main__":
    unittest.main()
