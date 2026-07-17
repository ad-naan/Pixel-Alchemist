from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageSequence


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate batch image output coverage, dimensions, and GIF metadata.")
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--variants", nargs="*")
    parser.add_argument("--languages", nargs="*", help="Backward-compatible alias.")
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    variants = payload.get("variants") or payload.get("locales") or [{"id": "default", "language": "default"}]
    requested = set(args.variants or args.languages or [str(item.get("id") or item.get("language") or "default") for item in variants])
    errors = []
    checked = 0
    for variant in variants:
        identifier = str(variant.get("id") or variant.get("language") or "default")
        if identifier not in requested and str(variant.get("language", "default")) not in requested:
            continue
        for template_name, template in payload.get("templates", {}).items():
            output = args.output_dir / identifier / str(template["output"])
            if not output.exists():
                errors.append(f"missing: {output}")
                continue
            with Image.open(output) as image:
                if image.size != tuple(template["canvas"]):
                    errors.append(f"size: {output}: {image.size} != {tuple(template['canvas'])}")
                if output.suffix.lower() == ".gif" and template.get("animation"):
                    expected = template["animation"]
                    if getattr(image, "n_frames", 1) != int(expected.get("frames", image.n_frames)):
                        errors.append(f"frames: {output}: {image.n_frames}")
                    if image.info.get("loop", 0) != int(expected.get("loop", image.info.get("loop", 0))):
                        errors.append(f"loop: {output}: {image.info.get('loop')}")
                    durations = [int(frame.info.get("duration", image.info.get("duration", 100))) for frame in ImageSequence.Iterator(image)]
                    if expected.get("durations_ms") and durations != [int(value) for value in expected["durations_ms"]]:
                        errors.append(f"durations: {output}: {durations}")
            checked += 1
    print(json.dumps({"checked": checked, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
