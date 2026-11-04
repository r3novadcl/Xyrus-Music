import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

SCALE = 512
FINAL = 128
CREAM = (250, 236, 216, 255)
GOLD = (238, 192, 92, 255)
TAN = (214, 168, 128, 255)
DARK = (58, 30, 18, 255)
TOP = (126, 72, 46)
BOTTOM = (72, 38, 24)


def point(x, y):
    return (x * SCALE / 100, y * SCALE / 100)


def pts(coords):
    return [point(x, y) for x, y in coords]


def base():
    image = Image.new("RGBA", (SCALE, SCALE), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (SCALE, SCALE))
    pixels = gradient.load()
    for y in range(SCALE):
        ratio = y / (SCALE - 1)
        colour = tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * ratio) for i in range(3)) + (255,)
        for x in range(SCALE):
            pixels[x, y] = colour
    mask = Image.new("L", (SCALE, SCALE), 0)
    ImageDraw.Draw(mask).ellipse([*point(5, 5), *point(95, 95)], fill=255)
    image.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    draw.ellipse([*point(5, 5), *point(95, 95)], outline=DARK, width=int(SCALE * 0.03))
    draw.ellipse([*point(8.5, 8.5), *point(91.5, 91.5)], outline=CREAM, width=int(SCALE * 0.035))
    return image, draw


def flower(draw):
    cx, cy, radius = 82, 82, 6.5
    for index in range(5):
        angle = math.radians(index * 72 - 90)
        px = cx + math.cos(angle) * radius
        py = cy + math.sin(angle) * radius
        draw.ellipse([*point(px - 5, py - 5), *point(px + 5, py + 5)], fill=CREAM, outline=DARK, width=3)
    draw.ellipse([*point(cx - 3.5, cy - 3.5), *point(cx + 3.5, cy + 3.5)], fill=TAN, outline=DARK, width=2)


def line_width(value=6):
    return int(SCALE * value / 100)


def tri_right(draw, x, y, size, fill=CREAM):
    draw.polygon(pts([(x, y - size), (x + size * 1.15, y), (x, y + size)]), fill=fill)


def tri_left(draw, x, y, size, fill=CREAM):
    draw.polygon(pts([(x, y - size), (x - size * 1.15, y), (x, y + size)]), fill=fill)


def bar(draw, x1, y1, x2, y2, fill=CREAM, radius=2):
    draw.rounded_rectangle([*point(x1, y1), *point(x2, y2)], radius=radius * SCALE / 100, fill=fill)


def star_points(cx, cy, outer, inner, spikes=5, rotation=-90):
    result = []
    for index in range(spikes * 2):
        radius = outer if index % 2 == 0 else inner
        angle = math.radians(rotation + index * 180 / spikes)
        result.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return result


def glyph_previous(draw):
    bar(draw, 28, 33, 35, 67)
    tri_left(draw, 70, 50, 17)


def glyph_skip(draw):
    bar(draw, 65, 33, 72, 67)
    tri_right(draw, 30, 50, 17)


def glyph_rewind(draw):
    tri_left(draw, 52, 50, 15)
    tri_left(draw, 76, 50, 15)


def glyph_forward(draw):
    tri_right(draw, 24, 50, 15)
    tri_right(draw, 48, 50, 15)


def glyph_pause(draw):
    bar(draw, 32, 30, 44, 70)
    bar(draw, 56, 30, 68, 70)


def glyph_stop(draw):
    bar(draw, 31, 31, 69, 69, radius=5)


def glyph_loop(draw):
    width = line_width(6)
    draw.arc([*point(26, 28), *point(74, 72)], start=200, end=340, fill=CREAM, width=width)
    draw.arc([*point(26, 28), *point(74, 72)], start=20, end=160, fill=CREAM, width=width)
    draw.polygon(pts([(66, 24), (80, 34), (62, 38)]), fill=CREAM)
    draw.polygon(pts([(34, 76), (20, 66), (38, 62)]), fill=CREAM)


def glyph_autoplay(draw):
    width = line_width(6)
    draw.ellipse([*point(20, 36), *point(52, 64)], outline=CREAM, width=width)
    draw.ellipse([*point(48, 36), *point(80, 64)], outline=CREAM, width=width)


def glyph_filters(draw):
    width = line_width(4.5)
    for x, knob in ((32, 38), (50, 62), (68, 44)):
        draw.line([point(x, 26), point(x, 74)], fill=CREAM, width=width)
        draw.ellipse([*point(x - 7, knob - 7), *point(x + 7, knob + 7)], fill=CREAM, outline=DARK, width=3)


def glyph_like(draw):
    draw.polygon(pts(star_points(50, 52, 27, 12)), fill=GOLD, outline=DARK)


def glyph_coin(draw):
    for offset in (14, 0, -14):
        draw.ellipse([*point(25, 38 + offset), *point(75, 58 + offset)], fill=GOLD, outline=DARK, width=4)
    draw.ellipse([*point(25, 24), *point(75, 44)], fill=GOLD, outline=DARK, width=4)
    draw.ellipse([*point(38, 30), *point(62, 38)], outline=DARK, width=4)


def glyph_plan(draw):
    glyph_coin(draw)


def glyph_free(draw):
    bar(draw, 28, 46, 72, 74, radius=3)
    bar(draw, 24, 36, 76, 48, radius=3)
    bar(draw, 46, 36, 54, 74, fill=GOLD, radius=1)
    draw.ellipse([*point(34, 22), *point(50, 38)], outline=CREAM, width=line_width(3.5))
    draw.ellipse([*point(50, 22), *point(66, 38)], outline=CREAM, width=line_width(3.5))


def glyph_boost(draw):
    draw.polygon(pts([(50, 22), (66, 50), (58, 50), (58, 66), (42, 66), (42, 50), (34, 50)]), fill=CREAM)
    draw.polygon(pts([(42, 70), (58, 70), (50, 80)]), fill=GOLD)


def glyph_danger(draw):
    draw.polygon(pts([(50, 22), (78, 72), (22, 72)]), fill=GOLD, outline=DARK)
    bar(draw, 47.5, 38, 52.5, 58, fill=DARK, radius=2)
    draw.ellipse([*point(46.5, 62), *point(53.5, 69)], fill=DARK)


def glyph_usage(draw):
    draw.ellipse([*point(34, 22), *point(66, 54)], fill=CREAM, outline=DARK, width=3)
    draw.polygon(pts([(40, 48), (60, 48), (50, 76)]), fill=CREAM)
    draw.ellipse([*point(44, 31), *point(56, 43)], fill=DARK)


def glyph_afk(draw):
    draw.ellipse([*point(26, 24), *point(70, 68)], fill=CREAM)
    draw.ellipse([*point(38, 18), *point(82, 62)], fill=(100, 56, 36, 255))
    draw.line([point(64, 52), point(76, 52), point(64, 64), point(76, 64)], fill=GOLD, width=line_width(3.5))
    draw.line([point(58, 36), point(66, 36), point(58, 44), point(66, 44)], fill=GOLD, width=line_width(2.5))


def glyph_spotify(draw):
    width = line_width(5)
    for index, span in enumerate((22, 17, 12)):
        top = 34 + index * 11
        draw.arc([*point(50 - span - 6, top), *point(50 + span + 6, top + 26)], start=200, end=340, fill=CREAM, width=width)


def glyph_soundcloud(draw):
    draw.ellipse([*point(26, 46), *point(48, 68)], fill=CREAM)
    draw.ellipse([*point(36, 34), *point(66, 64)], fill=CREAM)
    draw.ellipse([*point(54, 44), *point(76, 68)], fill=CREAM)
    bar(draw, 36, 54, 72, 68, radius=7)


def glyph_owner(draw):
    draw.polygon(pts([(24, 66), (24, 38), (38, 52), (50, 30), (62, 52), (76, 38), (76, 66)]), fill=GOLD, outline=DARK)
    bar(draw, 24, 66, 76, 74, fill=GOLD, radius=2)


def glyph_staff(draw):
    draw.polygon(pts([(50, 22), (74, 32), (72, 56), (50, 78), (28, 56), (26, 32)]), fill=CREAM, outline=DARK)
    draw.line([point(40, 50), point(48, 58), point(62, 40)], fill=(100, 56, 36, 255), width=line_width(5))


def glyph_premium(draw):
    draw.polygon(pts([(34, 34), (66, 34), (78, 48), (50, 78), (22, 48)]), fill=CREAM, outline=DARK)
    draw.line([point(22, 48), point(78, 48)], fill=TAN, width=line_width(2.5))
    draw.line([point(40, 34), point(34, 48), point(50, 78), point(66, 48), point(60, 34)], fill=TAN, width=line_width(2.5))


def glyph_noprefix(draw):
    draw.polygon(pts(star_points(50, 50, 28, 7, spikes=4, rotation=-90)), fill=GOLD, outline=DARK)
    draw.polygon(pts(star_points(72, 30, 9, 2.5, spikes=4, rotation=-90)), fill=CREAM)


GLYPHS = {
    "BTN_PREVIOUS": glyph_previous,
    "BTN_SKIP": glyph_skip,
    "BTN_REWIND": glyph_rewind,
    "BTN_FORWARD": glyph_forward,
    "BTN_PAUSE": glyph_pause,
    "BTN_STOP": glyph_stop,
    "BTN_LOOP": glyph_loop,
    "BTN_AUTOPLAY": glyph_autoplay,
    "BTN_FILTERS": glyph_filters,
    "BTN_LIKE": glyph_like,
    "COIN": glyph_coin,
    "PLAN": glyph_plan,
    "FREE": glyph_free,
    "BOOST": glyph_boost,
    "DANGER": glyph_danger,
    "USAGE": glyph_usage,
    "AFK": glyph_afk,
    "SPOTIFY": glyph_spotify,
    "SOUNDCLOUD": glyph_soundcloud,
    "BADGE_OWNER": glyph_owner,
    "BADGE_STAFF": glyph_staff,
    "BADGE_PREMIUM": glyph_premium,
    "BADGE_NOPREFIX": glyph_noprefix,
}


def render(key):
    image, draw = base()
    GLYPHS[key](draw)
    flower(draw)
    shadow = image.filter(ImageFilter.GaussianBlur(2))
    shadow.alpha_composite(image)
    return shadow.resize((FINAL, FINAL), Image.LANCZOS)


def main():
    import json

    entries = json.loads(config.EMOJIS_FILE.read_text(encoding="utf-8"))
    config.EMOJI_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    for key, glyph in GLYPHS.items():
        name = entries[key]["name"]
        render(key).save(config.EMOJI_LOCAL_DIR / f"{name}.png")
        print(f"generated {name}.png")


if __name__ == "__main__":
    main()
