from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inventory(root: Path, algorithm: str = "sha256") -> list[dict]:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        row = {
            "path": str(path),
            "relative": str(path.relative_to(root)),
            "suffix": path.suffix.lower(),
            "bytes": stat.st_size,
            "modified_ns": stat.st_mtime_ns,
            algorithm: digest(path, algorithm),
        }
        if path.suffix.lower() in IMAGE_SUFFIXES:
            try:
                with Image.open(path) as image:
                    row.update({
                        "kind": "image",
                        "size": list(image.size),
                        "mode": image.mode,
                        "format": image.format,
                        "frames": int(getattr(image, "n_frames", 1)),
                        "duration_ms": image.info.get("duration"),
                        "loop": image.info.get("loop"),
                    })
            except Exception as error:
                row.update({"kind": "image", "error": str(error)})
        elif path.suffix.lower() in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
            row["kind"] = "font"
        elif path.suffix.lower() in {".xlsx", ".xls", ".csv", ".tsv"}:
            row["kind"] = "spreadsheet"
        elif path.suffix.lower() == ".svg":
            row["kind"] = "vector"
        else:
            row["kind"] = "other"
        rows.append(row)
    return rows


def compare_inventory(current: list[dict], baseline: list[dict], algorithm: str) -> dict:
    current_index = {str(row["relative"]): row for row in current}
    baseline_index = {str(row["relative"]): row for row in baseline}
    added = sorted(current_index.keys() - baseline_index.keys())
    removed = sorted(baseline_index.keys() - current_index.keys())
    shared = current_index.keys() & baseline_index.keys()
    changed = sorted(
        relative
        for relative in shared
        if current_index[relative].get(algorithm) != baseline_index[relative].get(algorithm)
    )
    return {
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged_count": len(shared) - len(changed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory project images, fonts, workbooks, vectors, and related assets.")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--hash-algorithm", choices=["sha256", "sha1"], default="sha256")
    parser.add_argument("--baseline", type=Path, help="Compare hashes with a previous inventory JSON.")
    args = parser.parse_args()

    rows = inventory(args.root, args.hash_algorithm)
    payload = {"root": str(args.root.resolve()), "hash_algorithm": args.hash_algorithm, "files": rows}
    if args.baseline:
        baseline_payload = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline_algorithm = baseline_payload.get("hash_algorithm", "sha256")
        if baseline_algorithm != args.hash_algorithm:
            raise ValueError(
                f"baseline uses {baseline_algorithm}, current inventory uses {args.hash_algorithm}"
            )
        payload["changes"] = compare_inventory(rows, baseline_payload.get("files", []), args.hash_algorithm)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {len(rows)} entries -> {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
