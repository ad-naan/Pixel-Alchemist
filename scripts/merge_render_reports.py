from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    variant = str(row.get("variant") or "")
    template = str(row.get("template") or "")
    if not variant or not template:
        raise ValueError(f"render report row is missing variant/template: {row}")
    return variant, template


def indexed_rows(rows: list[Any], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError(f"{label} contains a non-object row")
        key = row_key(raw)
        if key in result:
            raise ValueError(f"{label} contains duplicate row {key}")
        result[key] = raw
    return result


def merge_rows(base_rows: list[Any], update_rows: list[Any]) -> list[dict[str, Any]]:
    base = indexed_rows(base_rows, "base report")
    updates = indexed_rows(update_rows, "update report")
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in base_rows:
        key = row_key(raw)
        replacement = updates.get(key)
        if replacement is None:
            merged.append(dict(raw))
        elif replacement.get("status") == "skipped" and "metrics" not in replacement and "metrics" in raw:
            merged.append({**raw, **replacement, "metrics": raw["metrics"]})
        else:
            merged.append(dict(replacement))
        seen.add(key)
    for raw in update_rows:
        key = row_key(raw)
        if key not in seen:
            merged.append(dict(raw))
            seen.add(key)
    return merged


def expected_keys(config: dict[str, Any]) -> set[tuple[str, str]]:
    variants = config.get("variants") or config.get("locales") or [{"id": "default", "language": "default"}]
    templates = config.get("templates", {})
    return {
        (str(variant.get("id") or variant.get("language") or "default"), str(template))
        for variant in variants
        for template in templates
    }


def load_rows(path: Path) -> list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"render report must be a JSON array: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge an incremental render report into a complete report by variant/template key.")
    parser.add_argument("base_report", type=Path)
    parser.add_argument("update_report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="Require complete variant/template coverage from this batch config.")
    args = parser.parse_args()

    merged = merge_rows(load_rows(args.base_report), load_rows(args.update_report))
    actual = set(indexed_rows(merged, "merged report"))
    if args.config:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        expected = expected_keys(config)
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        if missing or unexpected:
            raise ValueError(f"merged report coverage mismatch; missing={missing}, unexpected={unexpected}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"merged {len(merged)} render rows -> {args.output}")


if __name__ == "__main__":
    main()
