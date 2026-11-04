<div align="center">

# Xyrus

**A feature-rich Discord music bot built with Python, discord.py 2.6 and Lavalink.**

Components V2 interface · Hybrid commands · Multi-node Lavalink · SQLite · Fully configurable

</div>

---

## Features

- **Music** with Lavalink v4 through wavelink: play, search, queue, loop, shuffle, seek, filters, autoplay, 24/7 mode, liked songs, playlists, song stats and artist queueing
- **Multiple search engines**: YouTube, YouTube Music, Spotify and SoundCloud, selectable per server
- **Now Playing card** generated with Pillow, plus two rows of player controls
- **Components V2 UI** across every command, with a category dropdown help menu and a stats panel
- **Hybrid commands**: every command works as a prefix command and as a slash command
- **Premium system** with coins, a shop, redeem codes and per-server bot profile customization
- **NoPrefix** access that can be granted to selected users
- **Utility and config tools**: AFK with ping tracking, server and user info, welcome panel, auto-react, auto-respond and ignore lists
- **Fun commands** with anime gifs
- **Team card** rendered as an image and editable by the bot owners
- **Emoji sync** that uploads every emoji as an application emoji on first start
- **Central configuration**: names, colours, links, plans, filters and emojis live in one place

## Commands

| Category | Commands |
| --- | --- |
| General | `balance` `buy` `help` `info` `invite` `ping` `profile` `redeem` `stats` `support` `teams` `vote` |
| Utility | `afk` `avatar` `banner` `joinmsg` `prefix` `serverbanner` `servericon` `serverinfo` |
| Music | `247` `artist` `autoplay` `clearqueue` `disconnect` `engine` `filters` `join` `liked` `loop` `nowplaying` `pause` `play` `playlist` `queue` `replay` `resume` `search` `seek` `shuffle` `skip` `songstats` `stop` `volume` |
| Config | `greet` `ignore` `react` `respond` |
| Premium | `botavatar` `botbanner` `botbio` `botname` `botreset` |
| Fun | `hug` `pat` `ship` `slap` |

Owner commands are hidden from the help menu and work with the prefix only. Run `.ownerhelp` to see every owner command with its description: `noprefix`, `premium`, `gencode`, `coins`, `team`, `sync` and `reload`.

## Project structure

```
xyrus/
├── main.py                 Bot class, prefix logic, error handling
├── config.py               Single place for every setting
├── emojis.json             Emoji sources (name, source ID, animated)
├── requirements.txt
├── .env.example
├── assets/
│   ├── fonts/              Fonts used by the image cards
│   └── emojis/             Local emoji images (uploaded before CDN sources)
├── cogs/
│   ├── general.py          Help, info, profile, economy, teams, stats
│   ├── utility.py          AFK, avatar, server info, prefix, join message
│   ├── music.py            Player, queue, playlists, 24/7, autoplay
│   ├── settings.py         Welcome panel, ignore, auto-react, auto-respond
│   ├── premium.py          Per-server bot profile commands
│   ├── fun.py              Gif actions and ship
│   ├── owner.py            Hidden owner commands
│   └── events.py           Guild logs and coin rewards
├── utils/
│   ├── db.py               SQLite layer
│   ├── ui.py               Components V2 building blocks
│   ├── music.py            Now Playing, filters, queue and search views
│   ├── images.py           Now Playing and team card rendering
│   ├── help_view.py        Help menu and mention reply
│   ├── stats_view.py       Stats panel
│   ├── emojis.py           Emoji lookup with fallbacks
│   ├── emoji_sync.py       Application emoji uploader
│   ├── helpers.py
│   └── checks.py
└── scripts/
    ├── emoji_uploader.py   Run the emoji sync manually
    └── generate_emojis.py  Redraw the themed icons in assets/emojis
```

## Requirements

- Python 3.11 or newer
- A Discord bot application with the **Message Content** and **Server Members** intents enabled
- A Lavalink v4 server with the [youtube-source](https://github.com/lavalink-devs/youtube-source) plugin (add LavaSrc for Spotify support)

## Setup

```bash
git clone <your-repository-url>
cd xyrus
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`, then start the bot:

```bash
python main.py
```

### Environment variables

| Variable | Description |
| --- | --- |
| `TOKEN` | Bot token |
| `OWNER_IDS` | Comma separated user IDs of the owners |
| `BOT_NAME` | Display name used across the interface |
| `DEFAULT_PREFIX` | Prefix used before a server sets its own |
| `SUPPORT_URL` `INVITE_URL` `VOTE_URL` `PREMIUM_PAGE_URL` | Links shown in buttons. The invite link is generated automatically when empty |
| `BANNER_URL` | Banner shown in the help menu and used as the Now Playing card backdrop |
| `ACCENT_COLOR` | Container accent colour in hex |
| `LAVALINK_NODES` | JSON list of nodes. If a node is down the others are used |
| `LOG_CHANNEL_ID` | Channel that receives server join and leave logs |
| `EMOJI_AUTO_SYNC` | Upload missing emojis on startup |
| `SYNC_ON_START` | Sync slash commands on startup. Prefer the `sync` owner command |

Discord attachment links expire. Re-upload the banner somewhere permanent when the link stops working and update `BANNER_URL`.

### Slash commands

Run `.sync` once as an owner to register the slash commands globally.

## Emojis

Every emoji used by the bot is listed in `emojis.json`.

- `source` is the ID of an existing custom emoji. The sync downloads it from the Discord CDN and uploads it to your application.
- A PNG or GIF named after the emoji `name` inside `assets/emojis/` is uploaded instead of the CDN source. The icons that ship in that folder were drawn with `scripts/generate_emojis.py` in the same chocolate theme.
- The result is written to `emojis_uploaded.json`, which the bot reads at runtime.
- When an emoji cannot be resolved, the fallback from `EMOJI_FALLBACKS` in `config.py` is shown.

The sync runs automatically at startup. To run it by hand:

```bash
python scripts/emoji_uploader.py
```

To swap an icon, replace the file in `assets/emojis/`, delete the old emoji from the Developer Portal and run the uploader again.

## Customization

Edit `config.py` to change:

- Names, colours, links and the default prefix
- Help categories, stats pages and badges
- Coin rewards and premium plans
- Search engines, audio filters and player limits
- Team roles and card text
- Welcome message defaults

## Premium and economy

Users earn coins by using commands and by adding the bot to a server. Coins buy user or server premium from `buy`. Owners can create codes with `gencode user|guild <days> [uses]` and use `-1` days for lifetime access.

## Notes

- Voice channel status uses the voice-status endpoint, so the bot needs permission to set channel status.
- Per-server profile commands need the bot to be allowed to edit its own server profile.
- Playlists and liked songs store track links and resolve them again when played.
