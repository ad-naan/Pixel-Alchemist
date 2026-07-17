from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import ImageFont, features


def resolve_path(value: str, config_dir: Path) -> Path:
    if value.startswith("@skill/"):
        return (Path(__file__).resolve().parent.parent / value.removeprefix("@skill/")).resolve()
    path = Path(value)
    return path if path.is_absolute() else (config_dir / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Pillow complex-text support and configured font files.")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--require-raqm", action="store_true")
    args = parser.parse_args()

    raqm = bool(features.check("raqm"))
    result = {
        "raqm": raqm,
        "raqm_version": features.version_feature("raqm") if raqm else None,
        "fribidi_version": features.version_feature("fribidi") if raqm else None,
        "harfbuzz_version": features.version_feature("harfbuzz") if raqm else None,
        "fonts": [],
    }
    failed = args.require_raqm and not raqm
    if args.config:
        payload = json.loads(args.config.read_text(encoding="utf-8"))
        config_dir = args.config.resolve().parent
        fonts = {}
        if payload.get("font_preset"):
            preset_path = resolve_path(str(payload["font_preset"]), config_dir)
            preset = json.loads(preset_path.read_text(encoding="utf-8"))
            fonts.update(preset.get("fonts", preset))
        direct_fonts = payload.get("fonts", payload if "templates" not in payload else {})
        for language, weights in direct_fonts.items():
            fonts[language] = {**fonts.get(language, {}), **weights}
        for language, weights in fonts.items():
            for weight, value in weights.items():
                path = resolve_path(str(value), config_dir)
                row = {"language": language, "weight": weight, "path": str(path), "exists": path.exists(), "loads": False}
                if path.exists():
                    try:
                        ImageFont.truetype(str(path), 24)
                        row["loads"] = True
                    except Exception as error:
                        row["error"] = str(error)
                failed = failed or not row["loads"]
                result["fonts"].append(row)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
