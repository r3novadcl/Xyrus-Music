from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import config


def font(name, size):
    try:
        return ImageFont.truetype(str(config.FONT_DIR / name), size)
    except OSError:
        return ImageFont.load_default(size=size)


def gradient(size, top, bottom):
    width, height = size
    base = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        colour = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=colour)
    return base


def background(size, backdrop=None):
    if backdrop and not config.CARD_BACKGROUND.exists():
        try:
            image = Image.open(BytesIO(backdrop)).convert("RGB")
            return ImageOps.fit(image, size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(config.CARD_BLUR))
        except OSError:
            return gradient(size, *config.CARD_GRADIENT)
    if config.CARD_BACKGROUND.exists():
        image = Image.open(config.CARD_BACKGROUND).convert("RGB")
        return ImageOps.fit(image, size, Image.LANCZOS)
    return gradient(size, *config.CARD_GRADIENT)


def rounded(image, radius):
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.size[0], image.size[1]], radius, fill=255)
    result = image.convert("RGBA")
    result.putalpha(mask)
    return result


def circle(image, size):
    image = ImageOps.fit(image.convert("RGBA"), (size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    image.putalpha(mask)
    return image


def wrap(draw, content, typeface, width, lines):
    words = content.split()
    result = []
    current = ""
    index = 0
    while index < len(words):
        candidate = f"{current} {words[index]}".strip()
        if draw.textlength(candidate, font=typeface) <= width:
            current = candidate
            index += 1
            continue
        if not current:
            current = words[index]
            index += 1
        result.append(current)
        current = ""
        if len(result) == lines:
            break
    if current and len(result) < lines:
        result.append(current)
    if index < len(words) and result:
        last = result[-1]
        while last and draw.textlength(last + "...", font=typeface) > width:
            last = last[:-1]
        result[-1] = last.rstrip() + "..."
    return result


def to_buffer(image):
    buffer = BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def render_now_playing(artwork, title, duration, backdrop=None):
    width, height = config.NP_CARD_SIZE
    canvas = background((width, height), backdrop).convert("RGBA")
    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 110))
    canvas = Image.alpha_composite(canvas, shade)
    margin = 30
    cover_size = height - margin * 2
    if artwork:
        try:
            cover = Image.open(BytesIO(artwork)).convert("RGB")
            cover = ImageOps.fit(cover, (cover_size, cover_size), Image.LANCZOS)
        except OSError:
            cover = Image.new("RGB", (cover_size, cover_size), (40, 28, 22))
    else:
        cover = Image.new("RGB", (cover_size, cover_size), (40, 28, 22))
    canvas.alpha_composite(rounded(cover, 26), (margin, margin))
    draw = ImageDraw.Draw(canvas)
    left = margin + cover_size + 34
    max_width = width - left - margin
    label_font = font(config.FONT_BOLD, 22)
    title_font = font(config.FONT_BOLD, 38)
    info_font = font(config.FONT_BOLD, 22)
    draw.text((left, 46), config.NP_CARD_LABEL, font=label_font, fill=(255, 255, 255, 235))
    lines = wrap(draw, title, title_font, max_width, 2)
    y = 84
    for line in lines:
        draw.text((left, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += 52
    draw.text((left, height - 66), f"Duration  •  {duration}", font=info_font, fill=(235, 225, 215, 230))
    return to_buffer(rounded(canvas, 36))


def render_team(bot_name, members):
    width = 1400
    card_height = 150
    gap = 22
    header = 400
    rows = (len(members) + 1) // 2
    height = header + rows * (card_height + gap) + 90
    canvas = gradient((width, height), (62, 40, 30), (28, 17, 13))
    draw = ImageDraw.Draw(canvas, "RGBA")
    pad = 80
    draw.text((pad, 70), config.TEAM_HEADER.format(bot=bot_name.upper()), font=font(config.FONT_BOLD, 20), fill=(235, 215, 200, 255))
    draw.text((pad, 100), "THE TEAM", font=font(config.FONT_BOLD, 104), fill=(255, 255, 255, 255))
    draw.text((pad, 238), config.TEAM_TAGLINE.format(bot=bot_name), font=font(config.FONT_REGULAR, 26), fill=(230, 210, 195, 230))
    px = pad
    pill_font = font(config.FONT_BOLD, 17)
    for role in config.TEAM_ROLES:
        colour = config.TEAM_ROLE_COLORS[role]
        label = role.upper()
        pill_width = int(draw.textlength(label, font=pill_font)) + 70
        draw.rounded_rectangle([px, 300, px + pill_width, 340], 20, fill=(255, 255, 255, 22))
        draw.text((px + 28, 308), label, font=pill_font, fill=colour + (255,))
        px += pill_width + 16
    box_x = width - pad - 330
    draw.rounded_rectangle([box_x, 70, width - pad, 190], 28, fill=(255, 255, 255, 22))
    draw.text((box_x + 26, 90), "TEAM MEMBERS", font=font(config.FONT_BOLD, 16), fill=(225, 190, 170, 255))
    draw.text((box_x + 26, 120), f"{len(members):02d}", font=font(config.FONT_BOLD, 52), fill=(255, 255, 255, 255))
    draw.text((box_x + 120, 152), config.TEAM_CREW.format(bot=bot_name.upper()), font=font(config.FONT_BOLD, 13), fill=(225, 190, 170, 255))
    draw.line([(pad, 372), (width - pad, 372)], fill=(255, 255, 255, 40), width=2)
    column = (width - pad * 2 - 30) // 2
    name_font = font(config.FONT_BOLD, 32)
    small_font = font(config.FONT_REGULAR, 18)
    role_font = font(config.FONT_BOLD, 16)
    for index, member in enumerate(members):
        x = pad + (index % 2) * (column + 30)
        y = header + (index // 2) * (card_height + gap)
        colour = config.TEAM_ROLE_COLORS.get(member["role"], (200, 200, 200))
        draw.rounded_rectangle([x, y, x + column, y + card_height], 24, fill=(255, 255, 255, 18))
        draw.rounded_rectangle([x, y + 8, x + 8, y + card_height - 8], 4, fill=colour + (255,))
        avatar = None
        if member.get("avatar"):
            try:
                avatar = Image.open(BytesIO(member["avatar"])).convert("RGB")
            except OSError:
                avatar = None
        if avatar is None:
            avatar = Image.new("RGB", (100, 100), (70, 50, 40))
        ring = 108
        draw.ellipse([x + 30, y + 21, x + 30 + ring, y + 21 + ring], outline=colour + (255,), width=4)
        badge = circle(avatar, ring - 12)
        canvas.paste(badge, (x + 36, y + 27), badge)
        text_x = x + 164
        draw.text((text_x, y + 18), member["name"][:22], font=name_font, fill=(255, 255, 255, 255))
        draw.text((text_x, y + 62), f"@{member['handle']}", font=small_font, fill=(205, 185, 170, 255))
        label = member["role"].upper()
        label_width = int(draw.textlength(label, font=role_font)) + 44
        draw.rounded_rectangle([text_x, y + 98, text_x + label_width, y + 128], 15, fill=(255, 255, 255, 26))
        draw.text((text_x + 22, y + 103), label, font=role_font, fill=colour + (255,))
        draw.text((x + column - 24, y + 104), str(member["id"]), font=font(config.FONT_REGULAR, 15), fill=(190, 170, 155, 200), anchor="ra")
    draw.text((pad, height - 56), config.TEAM_FOOTER.format(bot=bot_name.upper()), font=font(config.FONT_BOLD, 14), fill=(200, 175, 160, 200))
    draw.text((width - pad, height - 56), bot_name.lower(), font=font(config.FONT_BOLD, 14), fill=(200, 175, 160, 200), anchor="ra")
    return to_buffer(rounded(canvas, 40))
