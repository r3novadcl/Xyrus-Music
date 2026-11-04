import re
import time
from urllib.parse import urlparse

import config

LIFETIME = -1


def now():
    return int(time.time())


def active(until):
    return until == LIFETIME or until > now()


def extend_until(current, days):
    if current == LIFETIME or days == LIFETIME:
        return LIFETIME
    base = current if current > now() else now()
    return base + days * 86400


def number(value):
    return f"{int(value):,}"


def chips(values):
    return ", ".join(f"`{value}`" for value in values)


def clip(text, limit):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."


def quote(*lines):
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def fmt_duration(milliseconds):
    seconds = int(milliseconds // 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def fmt_uptime(seconds):
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def fmt_expiry(until):
    if until == LIFETIME:
        return "Lifetime"
    if until <= now():
        return "Inactive"
    return f"<t:{until}:R>"


def parse_time(text):
    text = text.strip().lower()
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        if len(parts) > 3 or not all(part.isdigit() for part in parts):
            return None
        total = 0
        for part in parts:
            total = total * 60 + int(part)
        return total * 1000
    if text.isdigit():
        return int(text) * 1000
    matches = re.findall(r"(\d+)\s*([hms])", text)
    if not matches or "".join(f"{a}{b}" for a, b in matches) != re.sub(r"\s+", "", text):
        return None
    units = {"h": 3600, "m": 60, "s": 1}
    return sum(int(amount) * units[unit] for amount, unit in matches) * 1000


def is_url(text):
    try:
        parsed = urlparse(text)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def invite_url(bot):
    if config.INVITE_URL:
        return config.INVITE_URL
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={bot.user.id}&permissions={config.INVITE_PERMISSIONS}"
        "&scope=bot%20applications.commands"
    )


def apply_variables(text, member):
    if not text:
        return text
    guild = member.guild
    icon = guild.icon.url if guild.icon else ""
    replacements = {
        "{user}": member.mention,
        "{username}": member.name,
        "{server}": guild.name,
        "{memberCount}": str(guild.member_count),
        "{user_avatar}": member.display_avatar.url,
        "{server_icon}": icon,
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text
