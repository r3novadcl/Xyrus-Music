import asyncio

import discord
import wavelink

import config
from utils import ui
from utils.emojis import E
from utils.helpers import clip, fmt_duration, is_url, now, quote
from utils.images import render_now_playing

CARD_NAME = "nowplaying.png"
LOOP_ORDER = [wavelink.QueueMode.normal, wavelink.QueueMode.loop, wavelink.QueueMode.loop_all]
LOOP_LABELS = {
    wavelink.QueueMode.normal: "Off",
    wavelink.QueueMode.loop: "Track",
    wavelink.QueueMode.loop_all: "Queue",
}


def source_info(track):
    source = str(getattr(track, "source", "") or "").lower().replace(" ", "")
    return config.SOURCES.get(source, config.SOURCES["default"])


def requester_id(track):
    return getattr(track.extras, "requester", None)


def tag_requester(track, user_id):
    track.extras = {"requester": user_id}


def track_line(index, track):
    return f"`{index}.` [{clip(track.title, 60)}]({track.uri}) • `{fmt_duration(track.length)}`"


async def fetch_bytes(bot, url):
    if not url:
        return None
    try:
        async with bot.session.get(url) as response:
            if response.status == 200:
                return await response.read()
    except Exception:
        return None
    return None


async def card_backdrop(bot):
    if config.CARD_BACKGROUND.exists() or not config.BANNER_URL:
        return None
    if getattr(bot, "backdrop", None) is None:
        bot.backdrop = await fetch_bytes(bot, config.BANNER_URL)
    return bot.backdrop


async def build_card(bot, track):
    artwork = await fetch_bytes(bot, track.artwork)
    backdrop = await card_backdrop(bot)
    try:
        buffer = await asyncio.to_thread(
            render_now_playing, artwork, track.title, fmt_duration(track.length), backdrop
        )
    except Exception:
        return None
    return discord.File(buffer, filename=CARD_NAME)


async def set_voice_status(bot, channel, status):
    if not config.VOICE_STATUS or channel is None:
        return
    route = discord.http.Route("PUT", "/channels/{channel_id}/voice-status", channel_id=channel.id)
    attempts = [f"{E('PLAYING')} {status}", status] if status else [""]
    for attempt in attempts:
        try:
            await bot.http.request(route, json={"status": attempt})
            return
        except discord.HTTPException:
            continue


async def search_tracks(bot, guild_id, query):
    if is_url(query):
        return await wavelink.Playable.search(query)
    engine = await bot.db.guild_value(guild_id, "engine", config.DEFAULT_ENGINE)
    prefix = config.ENGINES.get(engine, config.ENGINES[config.DEFAULT_ENGINE])["prefix"]
    return await wavelink.Playable.search(query, source=prefix)


async def apply_filters(player, keys):
    filters = wavelink.Filters()
    for key in keys:
        for name, value in config.FILTERS[key].items():
            if name == "label":
                continue
            if name == "equalizer":
                filters.equalizer.set(bands=[{"band": band, "gain": gain} for band, gain in value])
            else:
                getattr(filters, name).set(**value)
    await player.set_filters(filters)
    player.xy_filters = set(keys)


async def stop_player(bot, player):
    player.queue.clear()
    keep = await bot.db.guild_value(player.guild.id, "vc247", 0)
    await player.skip(force=True)
    await set_voice_status(bot, player.channel, "")
    if not keep:
        await player.disconnect()


async def delete_now_playing(player):
    message = getattr(player, "np_message", None)
    player.np_message = None
    if message:
        try:
            await message.delete()
        except discord.HTTPException:
            pass


class NowPlayingView(ui.BaseView):
    def __init__(self, bot, player, track, requester, card=True):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player
        self.track = track
        self.requester = requester
        self.card = card
        self.add_item(self.build())

    async def interaction_check(self, interaction):
        voice = getattr(interaction.user, "voice", None)
        if not voice or voice.channel != self.player.channel:
            await interaction.response.send_message(
                view=ui.failure("You need to be in my voice channel to use these controls."), ephemeral=True
            )
            return False
        return True

    def build(self):
        track = self.track
        info = source_info(track)
        head = f"# {E('PLAYING')} Now Playing\n### **{clip(track.title, 200)}**"
        top = ui.section(head, ui.thumb(track.artwork)) if track.artwork else ui.text(head)
        details = ui.text(
            quote(
                f"{E('DOT')} **Author:** `{track.author}`",
                f"{E('DOT')} **Duration:** `{fmt_duration(track.length)}`",
                f"{E('DOT')} **Source:** {E(info['emoji'])} [{info['action']}]({track.uri})",
            )
        )
        items = [top, details]
        if self.card:
            items.append(ui.gallery(f"attachment://{CARD_NAME}"))
        items.append(ui.text(f"-# Request by: {self.requester}"))
        items.append(ui.sep())
        player = self.player
        playing = not player.paused
        looping = player.queue.mode != wavelink.QueueMode.normal
        autoplay = getattr(player, "xy_autoplay", False)
        primary = discord.ButtonStyle.success
        plain = discord.ButtonStyle.secondary
        items.append(
            ui.row(
                ui.button(emoji=E.partial("BTN_AUTOPLAY"), style=primary if autoplay else plain, callback=self.on_autoplay),
                ui.button(emoji=E.partial("BTN_PREVIOUS"), callback=self.on_previous),
                ui.button(emoji=E.partial("BTN_PAUSE"), style=primary if playing else plain, callback=self.on_pause),
                ui.button(emoji=E.partial("BTN_SKIP"), callback=self.on_skip),
                ui.button(emoji=E.partial("BTN_LOOP"), style=primary if looping else plain, callback=self.on_loop),
            )
        )
        items.append(
            ui.row(
                ui.button(emoji=E.partial("BTN_FILTERS"), callback=self.on_filters),
                ui.button(emoji=E.partial("BTN_REWIND"), callback=self.on_rewind),
                ui.button(emoji=E.partial("BTN_STOP"), callback=self.on_stop),
                ui.button(emoji=E.partial("BTN_FORWARD"), callback=self.on_forward),
                ui.button(emoji=E.partial("BTN_LIKE"), callback=self.on_like),
            )
        )
        return ui.box(*items)

    async def refresh(self, interaction):
        await self.redraw(interaction, self.build())

    async def on_autoplay(self, interaction):
        enabled = not getattr(self.player, "xy_autoplay", False)
        self.player.xy_autoplay = enabled
        await self.bot.db.guild_set(self.player.guild.id, autoplay=int(enabled))
        await self.refresh(interaction)

    async def on_previous(self, interaction):
        history = self.player.queue.history
        if history is None or len(history) < 2:
            await interaction.response.send_message(view=ui.failure("There is no previous track."), ephemeral=True)
            return
        previous = history[-2]
        current = self.player.current
        if current:
            self.player.queue.put_at(0, current)
        await interaction.response.defer()
        await self.player.play(previous, add_history=False)

    async def on_pause(self, interaction):
        await self.player.pause(not self.player.paused)
        await self.refresh(interaction)

    async def on_skip(self, interaction):
        await interaction.response.defer()
        await self.player.skip(force=True)

    async def on_loop(self, interaction):
        index = LOOP_ORDER.index(self.player.queue.mode)
        self.player.queue.mode = LOOP_ORDER[(index + 1) % len(LOOP_ORDER)]
        await self.refresh(interaction)

    async def on_filters(self, interaction):
        view = FiltersView(self.bot, self.player, interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def on_rewind(self, interaction):
        await self.player.seek(max(self.player.position - config.SEEK_STEP_MS, 0))
        await interaction.response.defer()

    async def on_forward(self, interaction):
        target = min(self.player.position + config.SEEK_STEP_MS, max(self.track.length - 1000, 0))
        await self.player.seek(target)
        await interaction.response.defer()

    async def on_stop(self, interaction):
        await interaction.response.defer()
        await delete_now_playing(self.player)
        await stop_player(self.bot, self.player)

    async def on_like(self, interaction):
        track = self.track
        await self.bot.db.run(
            "INSERT OR REPLACE INTO liked (user_id, uri, title, author, length, added) VALUES (?, ?, ?, ?, ?, ?)",
            interaction.user.id,
            track.uri,
            track.title,
            track.author,
            track.length,
            now(),
        )
        await interaction.response.send_message(
            view=ui.success(f"Added **{clip(track.title, 100)}** to your liked songs."), ephemeral=True
        )


class FiltersView(ui.BaseView):
    def __init__(self, bot, player, author_id):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.player = player
        self.add_item(self.build())

    def build(self):
        active = getattr(self.player, "xy_filters", set())
        options = [discord.SelectOption(label="Clear Filters", value="clear")]
        for key, spec in config.FILTERS.items():
            options.append(discord.SelectOption(label=spec["label"], value=key, default=key in active))
        lines = [f"{E('DOT')} **Note:** It might take a few seconds for the filter to apply."]
        if active:
            names = ", ".join(config.FILTERS[key]["label"] for key in config.FILTERS if key in active)
            lines.append(f"{E('DOT')} **Active:** {names}")
        body = (
            "# Music Filters\n**Audio Filters Menu**\n"
            "Select a filter from the dropdown below to apply it to the music. "
            "You can stack some filters or clear them completely.\n\n"
            + quote(*lines)
        )
        return ui.box(
            ui.text(body),
            ui.row(ui.select("Select an audio filter to apply...", options, self.on_select)),
        )

    async def on_select(self, interaction):
        value = interaction.data["values"][0]
        active = set(getattr(self.player, "xy_filters", set()))
        if value == "clear":
            active = set()
        elif value in active:
            active.discard(value)
        else:
            active.add(value)
        await interaction.response.defer()
        await apply_filters(self.player, active)
        self.clear_items()
        self.add_item(self.build())
        await interaction.edit_original_response(view=self)


class QueueView(ui.BaseView):
    def __init__(self, guild, player, author_id):
        super().__init__(author_id=author_id)
        self.guild = guild
        self.player = player
        self.page = 0
        self.add_item(self.build())

    @property
    def tracks(self):
        return list(self.player.queue)

    @property
    def pages(self):
        return max((len(self.tracks) + config.QUEUE_PAGE_SIZE - 1) // config.QUEUE_PAGE_SIZE, 1)

    def build(self):
        current = self.player.current
        size = config.QUEUE_PAGE_SIZE
        tracks = self.tracks
        start = self.page * size
        chunk = tracks[start : start + size]
        items = [ui.text(f"# Queue List For {self.guild.name}")]
        if current:
            items.append(ui.text(quote(f"**Now Playing:** [{clip(current.title, 100)}]({current.uri})")))
        if chunk:
            items.append(ui.text("\n".join(track_line(start + i + 1, t) for i, t in enumerate(chunk))))
        else:
            items.append(ui.text(quote("No more tracks in queue.")))
        items.append(ui.text(f"-# Page {self.page + 1}/{self.pages} • {len(tracks)} queued tracks"))
        if self.pages > 1:
            items.append(
                ui.row(
                    ui.button(label="Previous", callback=self.on_previous, disabled=self.page == 0),
                    ui.button(label="Next", callback=self.on_next, disabled=self.page >= self.pages - 1),
                )
            )
        return ui.box(*items)

    async def on_previous(self, interaction):
        self.page = max(self.page - 1, 0)
        await self.redraw(interaction, self.build())

    async def on_next(self, interaction):
        self.page = min(self.page + 1, self.pages - 1)
        await self.redraw(interaction, self.build())


class SearchView(ui.BaseView):
    def __init__(self, author_id, tracks, on_pick):
        super().__init__(author_id=author_id)
        self.tracks = tracks
        self.on_pick = on_pick
        options = [
            discord.SelectOption(
                label=clip(track.title, 100),
                description=clip(f"{track.author} • {fmt_duration(track.length)}", 100),
                value=str(index),
            )
            for index, track in enumerate(tracks)
        ]
        lines = "\n".join(track_line(index + 1, track) for index, track in enumerate(tracks))
        self.add_item(
            ui.box(
                ui.text(f"# {E('MUSIC')} Search Results\n{lines}"),
                ui.row(ui.select("Select a track to play...", options, self.on_select)),
            )
        )

    async def on_select(self, interaction):
        track = self.tracks[int(interaction.data["values"][0])]
        await self.on_pick(interaction, track)
