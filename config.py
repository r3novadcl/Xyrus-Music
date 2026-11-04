import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=""):
    return os.getenv(name, "").strip() or default


def env_int(name, default=0):
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


def env_bool(name, default=False):
    value = env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_ids(name):
    return [int(part) for part in env(name).replace(" ", "").split(",") if part.isdigit()]


def env_nodes():
    raw = env("LAVALINK_NODES")
    if raw:
        try:
            return json.loads(raw)
        except ValueError:
            return []
    uri = env("LAVALINK_URI")
    if not uri:
        return []
    return [
        {
            "identifier": env("LAVALINK_NAME", "XyrusLL"),
            "uri": uri,
            "password": env("LAVALINK_PASSWORD", "youshallnotpass"),
        }
    ]


TOKEN = env("TOKEN")
OWNER_IDS = env_ids("OWNER_IDS")

BOT_NAME = env("BOT_NAME", "Xyrus")
VERSION = env("BOT_VERSION", "v1.0.0")
TEAM_NAME = env("TEAM_NAME", "Xyrus Devs")
DEFAULT_PREFIX = env("DEFAULT_PREFIX", ".")
PREFIX_MAX_LENGTH = 5
COMMAND_MODE = "Hybrid (Slash & Prefix)"
PRESENCE_TEXT = env("PRESENCE_TEXT", "{prefix}help | {servers} servers")

SUPPORT_URL = env("SUPPORT_URL", "https://discord.gg/zb29U3mYvF")
INVITE_URL = env("INVITE_URL")
VOTE_URL = env("VOTE_URL")
BANNER_URL = env(
    "BANNER_URL",
    "https://cdn.discordapp.com/attachments/1551152630099607555/1567006537833251037/xyrus-help.png?ex=6aea9c10&is=6ae94a90&hm=2685be6e05bd3e5077a5eb5bf7110f348d284e17cafbe7451363f2247abaf338&",
)
INVITE_PERMISSIONS = env_int("INVITE_PERMISSIONS", 8)

LEAD_DEVELOPERS = env("LEAD_DEVELOPERS", "Easy , Gojo")
CONTRIBUTORS = env("CONTRIBUTORS", "xyrus_devs_group")

ACCENT_COLOR = int(env("ACCENT_COLOR", "D9B99B").lstrip("#"), 16)

DB_PATH = BASE_DIR / env("DB_FILE", "data/xyrus.db")
EMOJIS_FILE = BASE_DIR / "emojis.json"
EMOJIS_UPLOADED_FILE = BASE_DIR / "emojis_uploaded.json"
EMOJI_LOCAL_DIR = BASE_DIR / "assets" / "emojis"
EMOJI_AUTO_SYNC = env_bool("EMOJI_AUTO_SYNC", True)
FONT_DIR = BASE_DIR / "assets" / "fonts"
FONT_REGULAR = "Poppins-Regular.ttf"
FONT_MEDIUM = "Poppins-Medium.ttf"
FONT_BOLD = "Poppins-Bold.ttf"
CARD_BACKGROUND = BASE_DIR / "assets" / "card_bg.png"
CARD_GRADIENT = ((58, 38, 28), (24, 15, 12))
CARD_BLUR = 14

SYNC_ON_START = env_bool("SYNC_ON_START", False)
VIEW_TIMEOUT = 180
MENTION_REPLY = True
LOG_CHANNEL_ID = env_int("LOG_CHANNEL_ID", 0)

COGS = [
    "cogs.general",
    "cogs.utility",
    "cogs.music",
    "cogs.settings",
    "cogs.premium",
    "cogs.fun",
    "cogs.owner",
    "cogs.events",
]

CATEGORIES = {
    "general": {"label": "General", "description": "General & Info commands", "emoji": "INFO"},
    "utility": {"label": "Utility", "description": "Utility commands", "emoji": "UTILITY"},
    "music": {"label": "Music", "description": "Music related commands", "emoji": "MUSIC"},
    "config": {"label": "Config", "description": "Bot Configuration", "emoji": "CONFIG"},
    "premium": {"label": "Premium", "description": "Premium features & commands", "emoji": "PREMIUM"},
    "fun": {"label": "Fun", "description": "Fun & Games commands", "emoji": "FUN"},
}
HOME_OPTION = {"label": "Home", "description": "Return to the main help menu", "emoji": "HELP"}
HELP_LIST_ORDER = ["music", "general", "utility", "config", "premium", "fun"]

STATS_PAGES = {
    "general": {"label": "General Stats", "description": "Servers, Users, Shards", "emoji": "INFO"},
    "owner": {"label": "Owner & Developer Info", "description": "Owner and Developer info", "emoji": "TEAM"},
    "system": {"label": "System Info", "description": "DB, RAM, CPU", "emoji": "INFO"},
    "ping": {"label": "Ping", "description": "Database & Websocket Latency", "emoji": "LATENCY"},
    "music": {"label": "Music Node", "description": "Lavalink Node status", "emoji": "MUSIC"},
}

COIN_PER_COMMAND = (1, 3)
COIN_GUILD_JOIN = 150
COIN_START = 0
BALANCE_SECTIONS = [
    {
        "emoji": "FREE",
        "title": "For Freebies :",
        "lines": ["Each cmd used (1-3 coins)", "Add me in server (150 coins)"],
    },
    {
        "emoji": "BOOST",
        "title": "For Rich boys :",
        "lines": ["Boost support server (1000 coins)", "Pay 1.5M UwU or 29.99 INR (1800 coins)"],
    },
    {
        "emoji": "DANGER",
        "title": "For Daredevils :",
        "lines": ["Beg ! May get u rich / blacklisted"],
    },
]
CURRENCY_NOTICE = "This isn't a real but an in-game currency. User discretion is advised."

PLANS_USER = [
    {"label": "7 Days Premium", "days": 7, "price": 2600},
    {"label": "28 Days Premium", "days": 28, "price": 3750},
    {"label": "86 Days Premium", "days": 86, "price": 4600},
    {"label": "Lifetime Premium", "days": -1, "price": 102000},
]
PLANS_GUILD = [
    {"label": "7 Days Premium", "days": 7, "price": 600},
    {"label": "28 Days Premium", "days": 28, "price": 1750},
    {"label": "86 Days Premium", "days": 86, "price": 2600},
    {"label": "Lifetime Premium", "days": -1, "price": 100000},
]
PREMIUM_PAGE_URL = env("PREMIUM_PAGE_URL", SUPPORT_URL)

BADGES = {
    "owner": {"label": "Owner", "emoji": "BADGE_OWNER"},
    "team": {"label": "Team", "emoji": "BADGE_STAFF"},
    "premium": {"label": "Premium", "emoji": "BADGE_PREMIUM"},
    "noprefix": {"label": "NoPrefix", "emoji": "BADGE_NOPREFIX"},
    "member": {"label": "Member", "emoji": "MEMBER"},
}

TEAM_ROLES = ["owner", "co-owner", "manager", "admin", "staff"]
TEAM_ROLE_COLORS = {
    "owner": (226, 160, 120),
    "co-owner": (214, 150, 118),
    "manager": (180, 200, 190),
    "admin": (150, 175, 215),
    "staff": (150, 205, 160),
}
TEAM_TAGLINE = "Built around music, community & the {bot} experience."
TEAM_HEADER = "{bot} / PEOPLE BEHIND THE BEAT"
TEAM_FOOTER = "{bot} • MUSIC BOT • OFFICIAL TEAM"
TEAM_CREW = "OFFICIAL {bot} CREW"

LAVALINK_NODES = env_nodes()
LAVALINK_CACHE = 100
DEFAULT_ENGINE = "youtube"
DEFAULT_VOLUME = 80
MAX_VOLUME = 150
INACTIVE_TIMEOUT = env_int("INACTIVE_TIMEOUT", 180)
SEARCH_RESULTS = 10
QUEUE_PAGE_SIZE = 10
SEEK_STEP_MS = 10000
ARTIST_TRACKS = 10
MAX_QUEUE_SIZE = 500
MAX_PLAYLISTS = 10
MAX_PLAYLIST_TRACKS = 100
MAX_LIKED = 500
DELETE_OLD_NOW_PLAYING = True
VOICE_STATUS = True
VOICE_STATUS_TEXT = "Listening to: {title}"
SONG_STATS_TOP = 5
NP_CARD_SIZE = (1000, 280)
NP_CARD_LABEL = "NOW PLAYING"

ENGINES = {
    "youtube": {"label": "YouTube", "prefix": "ytsearch", "emoji": "YOUTUBE"},
    "youtubemusic": {"label": "YouTube Music", "prefix": "ytmsearch", "emoji": "YOUTUBE"},
    "spotify": {"label": "Spotify", "prefix": "spsearch", "emoji": "SPOTIFY"},
    "soundcloud": {"label": "SoundCloud", "prefix": "scsearch", "emoji": "SOUNDCLOUD"},
}
SOURCES = {
    "youtube": {"action": "Listen on YouTube", "emoji": "YOUTUBE"},
    "youtubemusic": {"action": "Listen on YouTube Music", "emoji": "YOUTUBE"},
    "spotify": {"action": "Listen on Spotify", "emoji": "SPOTIFY"},
    "soundcloud": {"action": "Listen on SoundCloud", "emoji": "SOUNDCLOUD"},
    "default": {"action": "Listen Now", "emoji": "MUSIC"},
}

FILTERS = {
    "bassboost": {
        "label": "Bass Boost",
        "equalizer": [[0, 0.25], [1, 0.25], [2, 0.2], [3, 0.1]],
    },
    "trebleboost": {
        "label": "Treble Boost",
        "equalizer": [[10, 0.2], [11, 0.25], [12, 0.3], [13, 0.3], [14, 0.25]],
    },
    "nightcore": {"label": "Nightcore", "timescale": {"speed": 1.25, "pitch": 1.25, "rate": 1.0}},
    "vaporwave": {
        "label": "Vaporwave",
        "timescale": {"speed": 0.8, "pitch": 0.8, "rate": 1.0},
        "tremolo": {"frequency": 2.0, "depth": 0.3},
    },
    "8d": {"label": "8D Audio", "rotation": {"rotation_hz": 0.2}},
    "karaoke": {
        "label": "Karaoke",
        "karaoke": {"level": 1.0, "mono_level": 1.0, "filter_band": 220.0, "filter_width": 100.0},
    },
    "soft": {"label": "Soft", "low_pass": {"smoothing": 20.0}},
    "tremolo": {"label": "Tremolo", "tremolo": {"frequency": 4.0, "depth": 0.5}},
    "vibrato": {"label": "Vibrato", "vibrato": {"frequency": 4.0, "depth": 0.5}},
    "distortion": {
        "label": "Distortion",
        "distortion": {
            "sin_offset": 0.0,
            "sin_scale": 1.0,
            "cos_offset": 0.0,
            "cos_scale": 1.0,
            "tan_offset": 0.0,
            "tan_scale": 1.0,
            "offset": 0.0,
            "scale": 1.0,
        },
    },
}

FUN_API = "https://nekos.best/api/v2/{action}"
FUN_ACTIONS = {
    "hug": "**{author}** hugs **{target}**",
    "pat": "**{author}** pats **{target}**",
    "slap": "**{author}** slaps **{target}**",
}
FUN_CREDIT = "Powered by nekos.best"
SHIP_BAR_LENGTH = 10
SHIP_TIERS = [
    (20, "Not a good match."),
    (40, "There is a small spark."),
    (60, "Could work with some effort."),
    (80, "A really good match."),
    (101, "A perfect match made in heaven."),
]

WELCOME_DEFAULTS = {
    "title": "Welcome to {server}",
    "description": "Hey {user}, glad to have you here. You are member #{memberCount}.",
    "color": "D9B99B",
}
WELCOME_VARIABLES = ["{user}", "{username}", "{server}", "{memberCount}", "{user_avatar}", "{server_icon}"]
AUTO_RESPONSE_LIMIT = 25
AFK_PING_LIMIT = 10
IGNORE_LIST_LIMIT = 25
ROLE_LIST_LIMIT = 12

EMOJI_FALLBACKS = {
    "COIN": "🪙",
    "FREE": "🎁",
    "BOOST": "🚀",
    "DANGER": "⚠️",
    "USAGE": "📌",
    "AFK": "💤",
    "YOUTUBE": "▶️",
    "SPOTIFY": "🎵",
    "SOUNDCLOUD": "☁️",
    "PLAN": "🪙",
    "BTN_AUTOPLAY": "♾️",
    "BTN_PREVIOUS": "⏮️",
    "BTN_PAUSE": "⏯️",
    "BTN_SKIP": "⏭️",
    "BTN_LOOP": "🔁",
    "BTN_FILTERS": "🎛️",
    "BTN_REWIND": "⏪",
    "BTN_STOP": "⏹️",
    "BTN_FORWARD": "⏩",
    "BTN_LIKE": "⭐",
    "BADGE_OWNER": "👑",
    "BADGE_STAFF": "🛡️",
    "BADGE_PREMIUM": "💎",
    "BADGE_NOPREFIX": "✨",
}

OWNER_HELP = [
    {
        "title": "NoPrefix",
        "emoji": "UTILITY",
        "commands": [
            ("noprefix add <user> [days]", "Grant prefix-free access. No days means lifetime."),
            ("noprefix remove <user>", "Remove prefix-free access."),
            ("noprefix list", "List users with NoPrefix and their expiry."),
        ],
    },
    {
        "title": "Premium",
        "emoji": "PREMIUM",
        "commands": [
            ("premium user <user> [days]", "Grant premium to a user."),
            ("premium guild <guild_id> [days]", "Grant premium to a server."),
            ("premium revoke <user|guild> <id>", "Remove premium from a user or server."),
            ("premium list", "List all premium users and servers."),
            ("gencode <user|guild> <days> [uses]", "Create a redeem code. Use -1 days for lifetime."),
        ],
    },
    {
        "title": "Economy",
        "emoji": "COIN",
        "commands": [
            ("coins add <user> <amount>", "Add coins to a user."),
            ("coins remove <user> <amount>", "Remove coins from a user."),
        ],
    },
    {
        "title": "Team",
        "emoji": "TEAM",
        "commands": [
            ("team add <user> <role>", "Add or update a member on the teams card."),
            ("team remove <user>", "Remove a member from the teams card."),
            ("team list", "List all team members and roles."),
        ],
    },
    {
        "title": "System",
        "emoji": "SETTINGS",
        "commands": [
            ("sync", "Register the slash commands globally."),
            ("reload <cog>", "Reload a cog without restarting, for example music."),
        ],
    },
]
