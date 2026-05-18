import json
import sys
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# -- Config ------------------------------------------------------------------
HANDLE = "@imamalinspires"   

BASE_DIR     = Path(__file__).parent
FONTS_DIR    = BASE_DIR / "assets" / "fonts"
BG_DIR       = BASE_DIR / "assets" / "backgrounds"
OUTPUT_DIR   = BASE_DIR / "output_images"
QUOTES_FILE  = BASE_DIR / "quotes.json"

FONT_SERIF        = FONTS_DIR / "Lora.ttf"
FONT_SERIF_ITALIC = FONTS_DIR / "Lora-Italic.ttf"
FONT_SANS         = FONTS_DIR / "Poppins-Regular.ttf"
FONT_SANS_MED     = FONTS_DIR / "Poppins-Medium.ttf"
FONT_SANS_BOLD    = FONTS_DIR / "Poppins-Bold.ttf"

# Canvas sizes
IG_WIDTH,  IG_HEIGHT  = 1080, 1080
PIN_WIDTH, PIN_HEIGHT = 1000, 1500

# -- Theme -------------------------------------------------------------------
# A warm, calm palette. Each template is "a background + text zones".
DARK_THEME = {
    "bg_top":      (26, 32, 44),     # deep slate
    "bg_bottom":   (45, 55, 72),     # lighter slate
    "quote":       (237, 242, 247),  # near-white
    "accent":      (214, 178, 102),  # muted gold
    "muted":       (160, 174, 192),  # cool grey
    "ornament":    (214, 178, 102),  # gold ornament/quote-mark
}

LIGHT_THEME = {
    "bg_top":      (250, 247, 240),  # warm cream
    "bg_bottom":   (237, 229, 213),  # deeper warm
    "quote":       (28,  28,  28),   # near-black
    "accent":      (139, 90,  43),   # warm brown
    "muted":       (100, 100, 100),  # medium grey
    "ornament":    (139, 90,  43),   # warm brown
}

THEME = DARK_THEME  # default (backwards-compat)

# -- Dummy quote (used until quotes.json is ready) ---------------------------
DUMMY_QUOTE = {
    "id":         0,
    "text":       "Do not let your difficulties fill you with anxiety; "
                  "after all, it is only the dark of night that produces the dawn.",
    "author":     "Imam Ali (AS)",
    "source":     "Attributed",
    "saying_ref": "On Hope",
    "category":   "anxiety",
    "used":       False,
}


# -- Quote picker ------------------------------------------------------------
def pick_quote() -> dict:
    """
    Returns the first unused quote from quotes.json and marks it used.
    Falls back to DUMMY_QUOTE if the file doesn't exist yet.
    """
    if not QUOTES_FILE.exists():
        print("Warning: quotes.json not found -- using dummy quote.")
        return DUMMY_QUOTE

    quotes = json.loads(QUOTES_FILE.read_text(encoding="utf-8"))
    unused = [q for q in quotes if not q.get("used", False)]

    if not unused:
        print("All quotes used -- resetting the cycle...")
        for q in quotes:
            q["used"] = False
        unused = quotes

    chosen = unused[0]
    for q in quotes:
        if q["id"] == chosen["id"]:
            q["used"] = True

    QUOTES_FILE.write_text(
        json.dumps(quotes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f'Picked: "{chosen["text"][:55]}..."')
    return chosen


# -- Text helpers ------------------------------------------------------------
def _line_height(font: ImageFont.FreeTypeFont) -> int:
    """Consistent line height for a font (ascent + descent)."""
    ascent, descent = font.getmetrics()
    return ascent + descent


def wrap_text(draw, text, font, max_width):
    """
    Greedy word-wrap: returns a list of lines that each fit within max_width.
    """
    words = text.split()
    lines, current = [], ""

    for word in words:
        trial = word if not current else f"{current} {word}"
        width = draw.textlength(trial, font=font)
        if width <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_text(draw, text, font_path, box_w, box_h,
             max_size=72, min_size=30, line_spacing=1.32):
    """
    Finds the largest font size at which `text` wraps to fit inside
    box_w x box_h. Returns (font, lines, total_text_height).
    """
    for size in range(max_size, min_size - 1, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap_text(draw, text, font, box_w)
        lh = _line_height(font) * line_spacing
        total_h = lh * len(lines)
        if total_h <= box_h:
            return font, lines, total_h
    # Nothing fit -- return smallest and let it overflow gracefully
    font = ImageFont.truetype(str(font_path), min_size)
    lines = wrap_text(draw, text, font, box_w)
    return font, lines, _line_height(font) * line_spacing * len(lines)


def draw_lines(draw, lines, font, center_x, start_y, fill,
               line_spacing=1.32):
    """Draws a list of lines, horizontally centered on center_x."""
    lh = _line_height(font) * line_spacing
    y = start_y
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text((center_x - w / 2, y), line, font=font, fill=fill)
        y += lh
    return y  # y position after the last line


# -- Background --------------------------------------------------------------
def make_gradient(width, height, top_rgb, bottom_rgb):
    """Creates a smooth vertical gradient background."""
    base = Image.new("RGB", (width, height), top_rgb)
    top = Image.new("RGB", (width, height), bottom_rgb)
    mask = Image.new("L", (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base


def load_background(width, height, category=None, theme=None):
    """
    Returns a background canvas. If assets/backgrounds/<category>.jpg
    exists, it's used (cropped to fit). Otherwise a themed gradient.
    """
    if theme is None:
        theme = DARK_THEME
    if category:
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = BG_DIR / f"{category}{ext}"
            if candidate.exists():
                img = Image.open(candidate).convert("RGB")
                img = _cover_resize(img, width, height)
                overlay_color = (0, 0, 0) if theme is DARK_THEME else (255, 255, 255)
                blend = 0.45 if theme is DARK_THEME else 0.35
                overlay = Image.new("RGB", (width, height), overlay_color)
                return Image.blend(img, overlay, blend)
    return make_gradient(width, height, theme["bg_top"], theme["bg_bottom"])


def _cover_resize(img, target_w, target_h):
    """Resize+crop an image to exactly cover target dimensions."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


# -- Decorative elements -----------------------------------------------------
def draw_quote_mark(draw, x, y, size, color):
    """Draws a large decorative opening quotation mark."""
    font = ImageFont.truetype(str(FONT_SERIF), size)
    draw.text((x, y), "\u201C", font=font, fill=color)


def draw_divider(draw, center_x, y, width, color):
    """A short centered divider line with a small diamond in the middle."""
    half = width // 2
    draw.line([(center_x - half, y), (center_x - 14, y)], fill=color, width=2)
    draw.line([(center_x + 14, y), (center_x + half, y)], fill=color, width=2)
    # center diamond
    d = 5
    draw.polygon(
        [(center_x, y - d), (center_x + d, y), (center_x, y + d), (center_x - d, y)],
        fill=color,
    )


# -- Renderers ---------------------------------------------------------------
def render_instagram(quote: dict, handle: str, theme=None) -> Image.Image:
    """
    1080x1080 square. Layout:
        [ gold quote mark ]
        [ quote body -- big serif, centered ]
        [ divider ]
        [ author -- serif italic ]
        [ source, saying_ref -- small sans ]
        [ handle -- bottom, small sans ]
    """
    if theme is None:
        theme = DARK_THEME
    W, H = IG_WIDTH, IG_HEIGHT
    img = load_background(W, H, quote.get("category"), theme=theme)
    draw = ImageDraw.Draw(img)

    margin = 130
    box_w = W - margin * 2

    # Decorative opening quote mark
    draw_quote_mark(draw, margin - 10, 90, 150, theme["ornament"])

    # Quote body -- fit within the central zone
    quote_zone_h = 520
    font, lines, text_h = fit_text(
        draw, quote["text"], FONT_SERIF,
        box_w, quote_zone_h, max_size=78, min_size=34,
    )
    # vertically center the block around the canvas middle
    start_y = (H - text_h) / 2 - 30
    end_y = draw_lines(draw, lines, font, W / 2, start_y, theme["quote"])

    # Divider
    div_y = end_y + 36
    draw_divider(draw, W / 2, div_y, 150, theme["accent"])

    # Author -- serif italic
    author_font = ImageFont.truetype(str(FONT_SERIF_ITALIC), 40)
    aw = draw.textlength(quote["author"], font=author_font)
    author_y = div_y + 30
    draw.text((W / 2 - aw / 2, author_y), quote["author"],
              font=author_font, fill=theme["accent"])

    # Source line -- "Nahj al-Balagha, Saying 21"
    src_text = f"{quote['source']}  \u00B7  {quote['saying_ref']}"
    src_font = ImageFont.truetype(str(FONT_SANS), 26)
    sw = draw.textlength(src_text, font=src_font)
    draw.text((W / 2 - sw / 2, author_y + 58), src_text,
              font=src_font, fill=theme["muted"])

    # Handle -- bottom center
    handle_font = ImageFont.truetype(str(FONT_SANS_MED), 28)
    hw = draw.textlength(handle, font=handle_font)
    draw.text((W / 2 - hw / 2, H - 80), handle,
              font=handle_font, fill=theme["muted"])

    return img


def render_pinterest(quote: dict, handle: str, theme=None) -> Image.Image:
    """
    1000x1500 vertical. Same elements, more vertical breathing room,
    source and saying_ref on separate lines.
    """
    if theme is None:
        theme = DARK_THEME
    W, H = PIN_WIDTH, PIN_HEIGHT
    img = load_background(W, H, quote.get("category"), theme=theme)
    draw = ImageDraw.Draw(img)

    margin = 110
    box_w = W - margin * 2

    # Top label -- category as a small uppercase tag
    cat = quote.get("category", "").upper()
    if cat:
        tag_font = ImageFont.truetype(str(FONT_SANS_MED), 26)
        # letter-spacing by inserting thin spaces
        spaced = "\u2009".join(cat)
        tw = draw.textlength(spaced, font=tag_font)
        draw.text((W / 2 - tw / 2, 150), spaced,
                  font=tag_font, fill=theme["accent"])

    # Decorative quote mark
    draw_quote_mark(draw, W / 2 - 45, 210, 130, theme["ornament"])

    # Quote body
    quote_zone_h = 620
    font, lines, text_h = fit_text(
        draw, quote["text"], FONT_SERIF,
        box_w, quote_zone_h, max_size=74, min_size=34,
    )
    start_y = 380
    end_y = draw_lines(draw, lines, font, W / 2, start_y, theme["quote"])

    # Divider
    div_y = end_y + 50
    draw_divider(draw, W / 2, div_y, 160, theme["accent"])

    # Author
    author_font = ImageFont.truetype(str(FONT_SERIF_ITALIC), 44)
    aw = draw.textlength(quote["author"], font=author_font)
    author_y = div_y + 40
    draw.text((W / 2 - aw / 2, author_y), quote["author"],
              font=author_font, fill=theme["accent"])

    # Source + saying_ref on separate lines
    src_font = ImageFont.truetype(str(FONT_SANS), 28)
    s1w = draw.textlength(quote["source"], font=src_font)
    draw.text((W / 2 - s1w / 2, author_y + 64), quote["source"],
              font=src_font, fill=theme["muted"])
    s2w = draw.textlength(quote["saying_ref"], font=src_font)
    draw.text((W / 2 - s2w / 2, author_y + 102), quote["saying_ref"],
              font=src_font, fill=theme["muted"])

    # Handle -- bottom
    handle_font = ImageFont.truetype(str(FONT_SANS_MED), 30)
    hw = draw.textlength(handle, font=handle_font)
    draw.text((W / 2 - hw / 2, H - 110), handle,
              font=handle_font, fill=theme["muted"])

    return img


# -- Main pipeline -----------------------------------------------------------
def generate(quote: dict = None) -> dict:
    """
    Full run:
      1. Pick a quote (or use the one passed in)
      2. Render Instagram + Pinterest images with Pillow
      3. Save both to PNG
      4. Return file paths + the quote used
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if quote is None:
        quote = pick_quote()

    slug = quote["saying_ref"].lower().replace(" ", "_").replace(".", "")
    date = datetime.now().strftime("%Y%m%d")

    print("\nGenerating Instagram dark image (1080x1080)...")
    ig_dark = render_instagram(quote, HANDLE, theme=DARK_THEME)
    ig_dark_path = OUTPUT_DIR / f"instagram_{slug}_{date}_dark.jpg"
    ig_dark.save(ig_dark_path, "JPEG", quality=95)
    print(f"Saved: {ig_dark_path.name}")

    print("Generating Instagram light image (1080x1080)...")
    ig_light = render_instagram(quote, HANDLE, theme=LIGHT_THEME)
    ig_light_path = OUTPUT_DIR / f"instagram_{slug}_{date}_light.jpg"
    ig_light.save(ig_light_path, "JPEG", quality=95)
    print(f"Saved: {ig_light_path.name}")

    print("Generating Pinterest dark image (1000x1500)...")
    pin_dark = render_pinterest(quote, HANDLE, theme=DARK_THEME)
    pin_dark_path = OUTPUT_DIR / f"pinterest_{slug}_{date}_dark.jpg"
    pin_dark.save(pin_dark_path, "JPEG", quality=95)
    print(f"Saved: {pin_dark_path.name}")

    print("Generating Pinterest light image (1000x1500)...")
    pin_light = render_pinterest(quote, HANDLE, theme=LIGHT_THEME)
    pin_light_path = OUTPUT_DIR / f"pinterest_{slug}_{date}_light.jpg"
    pin_light.save(pin_light_path, "JPEG", quality=95)
    print(f"Saved: {pin_light_path.name}")

    return {
        "instagram_dark":  str(ig_dark_path),
        "instagram_light": str(ig_light_path),
        "pinterest_dark":  str(pin_dark_path),
        "pinterest_light": str(pin_light_path),
        "quote":           quote,
    }


# -- Entry point -------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("  Quote Image Generator  (Pillow)")
    print("=" * 50)

    result = generate()

    print("\nDone!")
    print(f"  Instagram (dark)  -> {result['instagram_dark']}")
    print(f"  Instagram (light) -> {result['instagram_light']}")
    print(f"  Pinterest (dark)  -> {result['pinterest_dark']}")
    print(f"  Pinterest (light) -> {result['pinterest_light']}")
    print(f'  Quote             -> "{result["quote"]["text"][:65]}..."')
