from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont


FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
LICENSE_NAMES = ("OFL.txt", "LICENSE.txt", "LICENSE", "LICENCE.txt", "COPYING")
SCRIPT_PROBES = {
    "latin": (0x0041, 0x0061),
    "latin_extended": (0x0100, 0x1EF9),
    "cyrillic": (0x0410, 0x044F),
    "arabic": (0x0627, 0x0645),
    "devanagari": (0x0915, 0x093E),
    "thai": (0x0E01, 0x0E32),
    "hiragana": (0x3042, 0x3093),
    "katakana": (0x30A2, 0x30F3),
    "hangul": (0xAC00, 0xD55C),
    "cjk": (0x4E00, 0x6587),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def decoded_name(record: Any) -> str | None:
    try:
        return record.toUnicode().strip() or None
    except Exception:
        return None


def name_value(font: TTFont, name_id: int) -> str | None:
    preferred: list[str] = []
    fallback: list[str] = []
    for record in font["name"].names:
        if record.nameID != name_id:
            continue
        value = decoded_name(record)
        if not value:
            continue
        (preferred if record.langID in {0x409, 0} else fallback).append(value)
    values = preferred or fallback
    return values[0] if values else None


def codepoints(font: TTFont) -> set[int]:
    if "cmap" not in font:
        return set()
    return {codepoint for table in font["cmap"].tables for codepoint in table.cmap}


def script_coverage(points: set[int]) -> list[str]:
    return [name for name, probes in SCRIPT_PROBES.items() if all(probe in points for probe in probes)]


def find_license(path: Path, root: Path) -> str | None:
    current = path.parent
    while current == root or root in current.parents:
        for name in LICENSE_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate.relative_to(root).as_posix()
        if current == root:
            break
        current = current.parent
    return None


def inspect_font(path: Path, root: Path) -> dict[str, Any]:
    font = TTFont(path, fontNumber=0, lazy=True)
    try:
        points = codepoints(font)
        axes = []
        if "fvar" in font:
            axes = [axis.axisTag for axis in font["fvar"].axes]
        return {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
            "family": name_value(font, 16) or name_value(font, 1),
            "subfamily": name_value(font, 17) or name_value(font, 2),
            "postscript_name": name_value(font, 6),
            "variable_axes": axes,
            "glyph_codepoints": len(points),
            "scripts": script_coverage(points),
            "license": find_license(path, root),
        }
    finally:
        font.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Index bundled font files for fast family, role, and script lookup.")
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    files: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in sorted(item for item in args.root.rglob("*") if item.is_file() and item.suffix.lower() in FONT_EXTENSIONS):
        try:
            files.append(inspect_font(path, args.root))
        except Exception as exc:
            errors.append({"path": path.relative_to(args.root).as_posix(), "error": str(exc)})

    families: dict[str, list[str]] = defaultdict(list)
    duplicates: dict[str, list[str]] = defaultdict(list)
    for item in files:
        families[str(item.get("family") or "unknown")].append(str(item["path"]))
        duplicates[str(item["sha256"])].append(str(item["path"]))
    report = {
        "root": str(args.root.resolve()),
        "font_count": len(files),
        "family_count": len(families),
        "families": dict(sorted(families.items())),
        "duplicate_hashes": {key: value for key, value in duplicates.items() if len(value) > 1},
        "errors": errors,
        "files": files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"font_count": len(files), "family_count": len(families), "errors": len(errors), "output": str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
