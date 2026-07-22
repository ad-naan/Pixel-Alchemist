from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageSequence

try:
    from .render_batch import save_gif_exact
except ImportError:
    from render_batch import save_gif_exact


STATIC_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
GIF_SUFFIXES = {".gif"}


def image_inputs(root: Path) -> tuple[Path, list[Path]]:
    if root.is_file():
        if root.suffix.lower() not in STATIC_SUFFIXES | GIF_SUFFIXES:
            raise ValueError(f"unsupported image: {root}")
        return root.parent, [root]
    if not root.is_dir():
        raise FileNotFoundError(root)
    return root, sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in STATIC_SUFFIXES | GIF_SUFFIXES)


def gif_metadata(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        frames = list(ImageSequence.Iterator(image))
        return {
            "frames": len(frames),
            "durations_ms": [int(frame.info.get("duration", image.info.get("duration", 100))) for frame in frames],
            "disposals": [int(getattr(frame, "disposal_method", image.info.get("disposal", 0))) for frame in frames],
            "loop": int(image.info.get("loop", 0)),
        }


def quantize_gif_frame(frame: Image.Image, colors: int) -> Image.Image:
    colors = max(2, min(256, int(colors)))
    rgba = frame.convert("RGBA")
    array = np.asarray(rgba)
    alpha = array[:, :, 3]
    if int(alpha.min()) < 255:
        opaque_colors = max(1, colors - 1)
        quantized = Image.fromarray(array[:, :, :3], "RGB").quantize(
            colors=opaque_colors,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        indices = np.asarray(quantized, dtype=np.uint16) + 1
        indices[alpha < 128] = 0
        result = Image.fromarray(indices.astype(np.uint8), "P")
        palette = [0, 0, 0] + list((quantized.getpalette() or [])[:765])
        result.putpalette(palette + [0] * (768 - len(palette)))
        result.info["transparency"] = 0
        return result
    return rgba.convert("RGB").quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG,
    )


def compress_gif(source: Path, destination: Path, budget: int, colors: list[int]) -> dict[str, Any]:
    expected = gif_metadata(source)
    with Image.open(source) as image:
        frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(image)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidate = destination.with_name(f".{destination.name}.candidate")
    try:
        for color_count in sorted({max(2, min(256, int(value))) for value in colors}, reverse=True):
            quantized = [quantize_gif_frame(frame, color_count) for frame in frames]
            save_gif_exact(
                candidate,
                quantized,
                expected["durations_ms"],
                expected["disposals"],
                expected["loop"],
            )
            actual = gif_metadata(candidate)
            if actual != expected:
                raise ValueError(f"GIF metadata changed for {source}: expected {expected}, got {actual}")
            size = candidate.stat().st_size
            if size < budget:
                candidate.replace(destination)
                return {
                    "codec": "GIF",
                    "colors": color_count,
                    "output_bytes": size,
                    "animation": actual,
                }
    finally:
        candidate.unlink(missing_ok=True)
    raise ValueError(f"cannot compress GIF below {budget} bytes without dropping below {min(colors)} colors: {source}")


def encode_static(image: Image.Image, codec: str, quality: int | None = None) -> bytes:
    stream = io.BytesIO()
    if codec == "PNG":
        image.save(stream, format="PNG", optimize=True, compress_level=9)
    elif codec == "JPEG":
        image.convert("RGB").save(stream, format="JPEG", quality=int(quality or 95), optimize=True, progressive=True)
    elif codec == "WEBP":
        image.save(stream, format="WEBP", quality=int(quality or 95), method=6)
    else:
        raise ValueError(f"unsupported codec: {codec}")
    return stream.getvalue()


def highest_quality(image: Image.Image, codec: str, budget: int, minimum: int, maximum: int = 95) -> tuple[int, bytes] | None:
    best: tuple[int, bytes] | None = None
    low, high = minimum, maximum
    while low <= high:
        quality = (low + high) // 2
        encoded = encode_static(image, codec, quality)
        if len(encoded) < budget:
            best = (quality, encoded)
            low = quality + 1
        else:
            high = quality - 1
    return best


def has_transparency(image: Image.Image) -> bool:
    if image.mode not in {"RGBA", "LA", "P"}:
        return False
    alpha = image.convert("RGBA").getchannel("A")
    return alpha.getextrema()[0] < 255


def compress_static(source: Path, destination: Path, budget: int, fallback: str, min_quality: int) -> tuple[Path, dict[str, Any], bytes]:
    with Image.open(source) as opened:
        image = opened.convert("RGBA") if has_transparency(opened) else opened.convert("RGB")
    suffix = source.suffix.lower()
    if suffix == ".png":
        encoded = encode_static(image, "PNG")
        if len(encoded) < budget:
            return destination, {"codec": "PNG", "lossless": True, "output_bytes": len(encoded)}, encoded

    alpha = has_transparency(image)
    if suffix in {".jpg", ".jpeg"}:
        codec = "JPEG"
    elif suffix == ".webp":
        codec = "WEBP"
    elif fallback == "jpeg":
        if alpha:
            raise ValueError(f"JPEG fallback cannot preserve transparency: {source}")
        codec = "JPEG"
    elif fallback == "webp":
        codec = "WEBP"
    elif fallback == "auto":
        codec = "WEBP" if alpha else "JPEG"
    else:
        raise ValueError(f"lossless output exceeds {budget} bytes and fallback is disabled: {source}")

    selected = highest_quality(image, codec, budget, min_quality)
    if selected is None:
        raise ValueError(f"cannot compress {source} below {budget} bytes at quality >= {min_quality}")
    quality, encoded = selected
    extension = ".jpg" if codec == "JPEG" else ".webp"
    destination = destination.with_suffix(extension)
    return destination, {"codec": codec, "quality": quality, "lossless": False, "output_bytes": len(encoded)}, encoded


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress static images and GIFs to strict per-file byte budgets while preserving dimensions and GIF timing metadata.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--static-max-bytes", type=int, default=200_000)
    parser.add_argument("--gif-max-bytes", type=int, default=1_000_000)
    parser.add_argument("--fallback-format", choices=["auto", "none", "jpeg", "webp"], default="auto")
    parser.add_argument("--min-quality", type=int, default=25)
    parser.add_argument("--gif-colors", type=int, nargs="+", default=[256, 224, 192, 160, 128, 96, 64, 48, 32])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if args.static_max_bytes <= 0 or args.gif_max_bytes <= 0:
        raise ValueError("byte budgets must be positive")
    if not 1 <= args.min_quality <= 95:
        raise ValueError("min-quality must be between 1 and 95")
    if args.input.resolve() == args.output_dir.resolve():
        raise ValueError("input and output directory must differ")

    source_root, sources = image_inputs(args.input)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    claimed_outputs: set[Path] = set()
    for source in sources:
        relative = source.relative_to(source_root)
        destination = args.output_dir / relative
        budget = args.gif_max_bytes if source.suffix.lower() == ".gif" else args.static_max_bytes
        row: dict[str, Any] = {
            "input": str(source),
            "relative": str(relative),
            "input_bytes": source.stat().st_size,
            "budget_bytes": budget,
        }
        try:
            with Image.open(source) as source_image:
                input_dimensions = list(source_image.size)
            if source.stat().st_size < budget:
                final_output = destination
                details = {"codec": source.suffix.removeprefix(".").upper(), "copied": True, "output_bytes": source.stat().st_size}
                if source.suffix.lower() == ".gif":
                    details["animation"] = gif_metadata(source)
                if final_output in claimed_outputs:
                    raise ValueError(f"multiple inputs resolve to the same output: {final_output}")
                final_output.parent.mkdir(parents=True, exist_ok=True)
                if final_output.exists() and not args.overwrite:
                    raise FileExistsError(final_output)
                shutil.copy2(source, final_output)
            elif source.suffix.lower() == ".gif":
                final_output = destination
                if final_output in claimed_outputs:
                    raise ValueError(f"multiple inputs resolve to the same output: {final_output}")
                if final_output.exists() and not args.overwrite:
                    raise FileExistsError(final_output)
                details = compress_gif(source, final_output, budget, args.gif_colors)
            else:
                final_output, details, encoded = compress_static(source, destination, budget, args.fallback_format, args.min_quality)
                if final_output in claimed_outputs:
                    raise ValueError(f"multiple inputs resolve to the same output: {final_output}")
                if final_output.exists() and not args.overwrite:
                    raise FileExistsError(final_output)
                final_output.parent.mkdir(parents=True, exist_ok=True)
                final_output.write_bytes(encoded)
            actual_bytes = final_output.stat().st_size
            if actual_bytes >= budget:
                raise ValueError(f"output is {actual_bytes} bytes, expected strictly less than {budget}: {final_output}")
            with Image.open(final_output) as output_image:
                output_dimensions = list(output_image.size)
                output_format = output_image.format
            if output_dimensions != input_dimensions:
                raise ValueError(f"dimensions changed from {input_dimensions} to {output_dimensions}: {final_output}")
            claimed_outputs.add(final_output)
            row.update(details)
            row["output_bytes"] = actual_bytes
            row["output"] = str(final_output)
            row["dimensions"] = output_dimensions
            row["output_format"] = output_format
            row["status"] = "ok"
            rows.append(row)
            print(f"[ok] {relative} -> {final_output.name} ({row['output_bytes']} bytes)", flush=True)
        except Exception as error:
            row.update({"status": "failed", "error": str(error)})
            rows.append(row)
            failures.append({"input": str(source), "error": str(error)})
            print(f"[failed] {relative}: {error}", file=sys.stderr, flush=True)

    report = {
        "input": str(args.input.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "strict_less_than": True,
        "static_max_bytes": args.static_max_bytes,
        "gif_max_bytes": args.gif_max_bytes,
        "files": rows,
        "failures": failures,
    }
    report_path = args.report or args.output_dir / "compression-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures:
        raise SystemExit(1)
    print(f"compressed {len(rows)} files -> {args.output_dir}")


if __name__ == "__main__":
    main()
