from __future__ import annotations

import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

from PIL import Image, features


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from layout import resolve_elements
from render_batch import apply_flow_boxes, draw_icon_text, draw_text_element, physical_alignment, resolved_direction


class LayoutResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.elements = {
            "headline": {"type": "text", "box": [590, 10, 300, 60]},
            "date": {"type": "text", "box": [620, 80, 220, 40]},
            "location": {"type": "icon_text", "box": [640, 130, 180, 40]},
        }

    def template(self, anchor_x: int) -> dict:
        elements = {role: {**spec, "box": [anchor_x if role == "headline" else spec["box"][0], *spec["box"][1:]]} for role, spec in self.elements.items()}
        return {
            "elements": elements,
            "alignment_groups": {
                "main": {"members": ["headline", "date", "location"], "edge": "left", "anchor_role": "headline"}
            },
        }

    def test_same_group_name_is_independent_per_template(self) -> None:
        portrait = resolve_elements("portrait", self.template(590), {})
        landscape = resolve_elements("landscape", self.template(57), {})
        self.assertEqual([portrait[role]["box"][0] for role in self.elements], [590, 590, 590])
        self.assertEqual([landscape[role]["box"][0] for role in self.elements], [57, 57, 57])

    def test_variant_overrides_apply_before_group_and_can_disable_it(self) -> None:
        variant = {
            "layout_overrides": {"portrait": {"headline": {"box": [610, 12, 280, 58]}}},
            "alignment_overrides": {"landscape": {"main": {"enabled": False}}},
        }
        portrait = resolve_elements("portrait", self.template(590), variant)
        landscape = resolve_elements("landscape", self.template(57), variant)
        self.assertEqual([portrait[role]["box"][0] for role in self.elements], [610, 610, 610])
        self.assertEqual(landscape["date"]["box"][0], 620)

    def test_right_and_center_edges_use_each_member_width(self) -> None:
        template = self.template(590)
        template["alignment_groups"]["main"] = {"members": ["headline", "date", "location"], "edge": "right", "position": 900}
        right = resolve_elements("portrait", template, {})
        self.assertEqual([right[role]["box"][0] for role in self.elements], [600, 680, 720])
        template["alignment_groups"]["main"].update(edge="center", position=600)
        center = resolve_elements("portrait", template, {})
        self.assertEqual([center[role]["box"][0] for role in self.elements], [450, 490, 510])

    def test_invalid_groups_fail_visibly(self) -> None:
        cases = [
            {"members": ["missing"], "edge": "left", "position": 10},
            {"members": ["headline"], "edge": "top", "position": 10},
            {"members": ["headline"], "edge": "left", "position": 10, "physical_align": "top"},
            {"members": ["headline"], "edge": "left", "position": 10, "anchor_role": "headline"},
        ]
        for group in cases:
            with self.subTest(group=group), self.assertRaises(ValueError):
                resolve_elements("portrait", {"elements": self.elements, "alignment_groups": {"bad": group}}, {})

    def test_direction_and_physical_alignment_are_independent(self) -> None:
        text = "أيام Product Summit 2026"
        self.assertEqual(resolved_direction(text, {"direction": "rtl"}), "rtl")
        self.assertEqual(physical_alignment(text, {"direction": "rtl", "physical_align": "left"}), "left")
        self.assertEqual(physical_alignment(text, {"align": "left"}), "right")
        self.assertEqual(physical_alignment(text, {"align": "force-left"}), "left")

    def test_text_and_icon_text_report_validator_metrics(self) -> None:
        canvas = Image.new("RGBA", (420, 120), "#000000")
        font_path = str(ROOT / "assets" / "fonts" / "poppins" / "Poppins-Regular.ttf")
        text_spec = {
            "box": [40, 20, 340, 80],
            "font_path": font_path,
            "max_font_size": 32,
            "min_font_size": 20,
            "max_lines": 2,
            "physical_align": "left",
            "color": "#FFFFFF",
        }
        metrics = draw_text_element(canvas, text="Measured text", language="en", spec=text_spec, fonts={}, base_dir=ROOT)
        expected = {
            "box", "safe_box", "ink_box", "line_boxes", "font_size", "max_font_size", "font_scale",
            "line_count", "max_lines", "content_height", "height_density", "direction", "physical_align",
        }
        self.assertTrue(expected.issubset(metrics))

        with tempfile.TemporaryDirectory() as temporary:
            icon_path = Path(temporary) / "icon.png"
            Image.new("RGBA", (16, 16), "#FFAA22").save(icon_path)
            icon_metrics = draw_icon_text(
                canvas,
                text="Location",
                language="en",
                spec={**text_spec, "icon": str(icon_path), "icon_size": [16, 16], "icon_side": "start"},
                fonts={},
                base_dir=ROOT,
            )
        self.assertTrue({"group_box", "icon_box", "text_box"}.issubset(icon_metrics))
        self.assertEqual(icon_metrics["group_box"][0], text_spec["box"][0])

    def test_group_physical_alignment_overrides_legacy_icon_group_alignment(self) -> None:
        template = {
            "elements": {
                "headline": {
                    "type": "text", "box": [40, 10, 300, 50], "align": "left",
                    "font_path": str(ROOT / "assets" / "fonts" / "poppins" / "Poppins-Regular.ttf"),
                    "max_font_size": 28, "min_font_size": 20, "max_lines": 1, "color": "#FFFFFF",
                },
                "location": {
                    "type": "icon_text", "box": [80, 65, 260, 40], "group_align": "right",
                    "font_path": str(ROOT / "assets" / "fonts" / "poppins" / "Poppins-Regular.ttf"),
                    "max_font_size": 22, "min_font_size": 16, "max_lines": 1, "color": "#FFFFFF",
                    "icon_size": [16, 16], "icon_side": "left",
                },
            },
            "alignment_groups": {
                "copy": {
                    "members": ["headline", "location"], "edge": "left", "anchor_role": "headline",
                    "physical_align": "left",
                }
            },
        }
        elements = resolve_elements("portrait", template, {})
        self.assertEqual(elements["location"]["physical_align"], "left")
        self.assertEqual(elements["location"]["group_align"], "right")
        canvas = Image.new("RGBA", (380, 120), "#000000")
        headline_metrics = draw_text_element(
            canvas, text="Product Summit", language="en", spec=elements["headline"], fonts={}, base_dir=ROOT
        )
        with tempfile.TemporaryDirectory() as temporary:
            icon_path = Path(temporary) / "pin.png"
            Image.new("RGBA", (16, 16), "#FFAA22").save(icon_path)
            location_metrics = draw_icon_text(
                canvas,
                text="Hall A",
                language="en",
                spec={**elements["location"], "icon": str(icon_path)},
                fonts={},
                base_dir=ROOT,
            )
        self.assertEqual(location_metrics["group_box"][0], headline_metrics["ink_box"][0])

    def test_grapheme_wrap_keeps_thai_combining_marks_with_base(self) -> None:
        canvas = Image.new("RGBA", (180, 240), "#000000")
        spec = {
            "box": [10, 10, 58, 210],
            "font_path": str(ROOT / "assets" / "fonts" / "kanit" / "Kanit-Regular.ttf"),
            "max_font_size": 28,
            "min_font_size": 28,
            "max_lines": 10,
            "wrap_strategy": "grapheme",
            "physical_align": "left",
            "color": "#FFFFFF",
        }
        metrics = draw_text_element(canvas, text="ก่ก่ก่ก่ก่ก่", language="th", spec=spec, fonts={}, base_dir=ROOT)
        self.assertGreater(metrics["line_count"], 1)
        self.assertTrue(all(not unicodedata.category(line[0]).startswith("M") for line in metrics["lines"] if line))

    def test_manual_wrap_only_uses_explicit_line_breaks(self) -> None:
        canvas = Image.new("RGBA", (180, 100), "#000000")
        spec = {
            "box": [10, 10, 40, 80],
            "font_path": str(ROOT / "assets" / "fonts" / "poppins" / "Poppins-Regular.ttf"),
            "max_font_size": 24,
            "min_font_size": 24,
            "max_lines": 3,
            "wrap_strategy": "manual",
            "color": "#FFFFFF",
        }
        with self.assertRaises(ValueError):
            draw_text_element(canvas, text="one two three", language="en", spec=spec, fonts={}, base_dir=ROOT)

    def test_prefer_single_line_shrinks_before_wrapping(self) -> None:
        canvas = Image.new("RGBA", (360, 120), "#000000")
        spec = {
            "box": [20, 20, 250, 80],
            "font_path": str(ROOT / "assets" / "fonts" / "poppins" / "Poppins-Regular.ttf"),
            "max_font_size": 34,
            "min_font_size": 18,
            "single_line_min_font_size": 18,
            "max_lines": 2,
            "prefer_single_line": True,
            "color": "#FFFFFF",
        }
        metrics = draw_text_element(
            canvas,
            text="Global finance leaders",
            language="en",
            spec=spec,
            fonts={},
            base_dir=ROOT,
        )
        self.assertEqual(metrics["line_count"], 1)
        self.assertEqual(metrics["fit_mode"], "single_line_preferred")
        self.assertTrue(metrics["single_line_possible"])

    def test_flow_box_uses_only_obstacles_that_cross_the_text_band(self) -> None:
        template = {"obstacles": {"hero": {"box": [220, 0, 100, 100], "padding": 10}}}
        elements = {
            "upper": {
                "type": "text", "box": [20, 20, 180, 40], "flow_box": [20, 20, 360, 40],
                "avoid_obstacles": ["hero"], "physical_align": "left",
            },
            "lower": {
                "type": "text", "box": [20, 130, 180, 40], "flow_box": [20, 130, 360, 40],
                "avoid_obstacles": ["hero"], "physical_align": "left",
            },
        }
        resolved = apply_flow_boxes(elements, template)
        self.assertEqual(resolved["upper"]["box"], [20, 20, 190, 40])
        self.assertEqual(resolved["lower"]["box"], [20, 130, 360, 40])

    @unittest.skipUnless(features.check("raqm"), "Pillow RAQM is required")
    def test_arabic_render_reports_left_physical_alignment(self) -> None:
        canvas = Image.new("RGBA", (420, 120), "#000000")
        spec = {
            "box": [40, 20, 340, 80],
            "font_path": str(ROOT / "assets" / "fonts" / "kufam" / "Kufam-Regular.ttf"),
            "max_font_size": 32,
            "min_font_size": 20,
            "max_lines": 2,
            "direction": "rtl",
            "physical_align": "left",
            "color": "#FFFFFF",
        }
        metrics = draw_text_element(canvas, text="أيام Product Summit 2026", language="ar", spec=spec, fonts={}, base_dir=ROOT)
        self.assertEqual(metrics["direction"], "rtl")
        self.assertEqual(metrics["physical_align"], "left")
        self.assertTrue(all(line[0] == 40 for line in metrics["line_boxes"]))


if __name__ == "__main__":
    unittest.main()
