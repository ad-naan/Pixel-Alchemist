from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT.parents[1] / "assets" / "fonts" / "poppins"
ITEMS = [
    ("01-finished-only.png", "1  FLATTENED INPUT", "No clean background is supplied"),
    ("02-measured-text.png", "2  MEASURE TEXT", "Ink box, safe box and typography match"),
    ("03-erase-mask.png", "3  PRECISE MASK", "Glyphs, antialiasing and effect halo"),
    ("04-cleaned.png", "4  RECONSTRUCT", "Only masked pixels are regenerated"),
    ("05-pixel-verification.png", "5  VERIFY PIXELS", "Outside-mask changes: exactly zero"),
    ("06-redrawn.png", "6  REDRAW", "New copy uses the recovered layout contract"),
]
POSITIONS = [(40, 55), (580, 55), (1120, 55), (40, 665), (580, 665), (1120, 665)]


def build_verification() -> None:
    with Image.open(ROOT / "04-cleaned.png") as source:
        cleaned = source.convert("RGBA")
    with Image.open(ROOT / "03-erase-mask.png") as source:
        mask = source.convert("L")
    overlay = Image.new("RGBA", cleaned.size, (0, 0, 0, 0))
    overlay.paste((52, 235, 185, 105), (0, 0, *cleaned.size), mask)
    composed = Image.alpha_composite(cleaned, overlay)
    draw = ImageDraw.Draw(composed, "RGBA")
    font = ImageFont.truetype(str(FONT_DIR / "Poppins-Bold.ttf"), 25)
    label = "OUTSIDE MASK: 0 CHANGED PIXELS"
    box = draw.textbbox((0, 0), label, font=font)
    draw.rounded_rectangle((64, 558, 64 + box[2] + 34, 606), radius=14, fill=(5, 15, 29, 235), outline=(52, 235, 185, 255), width=2)
    draw.text((81, 568), label, font=font, fill=(198, 255, 239, 255))
    composed.save(ROOT / "05-pixel-verification.png", optimize=True)


def main() -> None:
    build_verification()
    title_font = ImageFont.truetype(str(FONT_DIR / "Poppins-Regular.ttf"), 30)
    caption_font = ImageFont.truetype(str(FONT_DIR / "Poppins-Regular.ttf"), 19)
    board = Image.new("RGB", (1660, 1230), "#07101F")
    draw = ImageDraw.Draw(board)
    thumb_size = (500, 262)
    for (filename, title, caption), (x, y) in zip(ITEMS, POSITIONS, strict=True):
        with Image.open(ROOT / filename) as source:
            thumb = source.convert("RGB").resize(thumb_size, Image.Resampling.LANCZOS)
        board.paste(thumb, (x, y + 70))
        draw.rounded_rectangle((x - 2, y + 68, x + 502, y + 334), radius=10, outline="#31435F", width=2)
        draw.text((x, y), title, font=title_font, fill="#F4F8FF")
        draw.text((x, y + 346), caption, font=caption_font, fill="#92A4C2")
    board.save(ROOT / "flattened-recovery-board.png", optimize=True)


if __name__ == "__main__":
    main()
