from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT.parents[1] / "assets" / "fonts" / "poppins"
ITEMS = [
    ("01-clean-layout.png", "1  CLEAN LAYOUT", "Text-free production canvas"),
    ("02-before-text.png", "2  ORIGINAL TEXT", "Reference artwork to measure"),
    ("03-measured-ink.png", "3  MEASURED INK", "Observed non-background pixels"),
    ("04-safe-zones.png", "4  SAFE DRAWING ZONES", "Padded boxes used for fitting"),
    ("05-after-replacement.png", "5  REPLACED TEXT", "New copy, same layout contract"),
]
POSITIONS = [(40, 60), (580, 60), (1120, 60), (310, 675), (850, 675)]


def main() -> None:
    title_font = ImageFont.truetype(str(FONT_DIR / "Poppins-Regular.ttf"), 31)
    caption_font = ImageFont.truetype(str(FONT_DIR / "Poppins-Regular.ttf"), 20)
    board = Image.new("RGB", (1680, 1275), "#07101F")
    draw = ImageDraw.Draw(board)
    thumb_size = (500, 262)

    for (filename, title, caption), (x, y) in zip(ITEMS, POSITIONS, strict=True):
        with Image.open(ROOT / filename) as source:
            thumb = source.convert("RGB").resize(thumb_size, Image.Resampling.LANCZOS)
        board.paste(thumb, (x, y + 74))
        draw.rounded_rectangle((x - 2, y + 72, x + 502, y + 338), radius=10, outline="#31435F", width=2)
        draw.text((x, y), title, font=title_font, fill="#F4F8FF")
        draw.text((x, y + 350), caption, font=caption_font, fill="#92A4C2")

    board.save(ROOT / "process-board.png", optimize=True)


if __name__ == "__main__":
    main()
