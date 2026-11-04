import asyncio
import logging
import random
from typing import Literal, Optional

import discord
import wavelink
from discord.ext import commands

import config
from utils import music as mu
from utils import ui
from utils.emojis import E
from utils.helpers import clip, fmt_duration, now, parse_time, quote

log = logging.getLogger("music")


class EngineView(ui.BaseView):
    def __init__(self, bot, author, current):
        super().__init__(author_id=author.id)
        self.bot = bot
        self.author = author
        self.current = current
        self.add_item(self.build())

    def build(self):
        options = [
            discord.SelectOption(
                label=data["label"],
                value=key,
                emoji=E.partial(data["emoji"]),
                default=key == self.current,
            )
            for key, data in config.ENGINES.items()
        ]
        label = config.ENGINES[self.current]["label"]
        dot = E("DOT")
        return ui.box(
            ui.text(
                f"# {E('MUSIC')} Search Engine\n"
                f"{quote(dot + ' **Current:** `' + label + '`')}\n"
                "Select the source used when you search with plain text."
            ),
            ui.row(ui.select("Select a search engine...", options, self.on_select)),
        )

    async def on_select(self, interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                view=ui.failure("You need the **Manage Server** permission to change the engine."), ephemeral=True
            )
            return
        self.current = interaction.data["values"][0]
        await self.bot.db.guild_set(interaction.guild_id, engine=self.current)
        await self.redraw(interaction, self.build())


class Music(commands.Cog):
    category = "music"

    def __init__(self, bot):
        self.bot = bot
        self.restored = False
        self.leaving = set()

    async def cog_load(self):
        nodes = [
            wavelink.Node(identifier=item.get("identifier"), uri=item["uri"], password=item["password"])
            for item in config.LAVALINK_NODES
        ]
        if not nodes:
            log.warning("No Lavalink nodes configured")
            return
        try:
            await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=config.LAVALINK_CACHE)
        except Exception:
            log.exception("Could not connect to Lavalink")

    async def prepare(self, player, channel):
        player.home = channel
        player.np_message = None
        player.xy_filters = set()
        row = await self.bot.db.one("SELECT volume, autoplay, vc247 FROM guilds WHERE guild_id = ?", player.guild.id)
        volume = row["volume"] if row and row["volume"] is not None else config.DEFAULT_VOLUME
        player.xy_autoplay = bool(row["autoplay"]) if row else False
        player.autoplay = wavelink.AutoPlayMode.partial
        player.inactive_timeout = None if row and row["vc247"] else config.INACTIVE_TIMEOUT
        await player.set_volume(volume)

    async def get_player(self, ctx, connect=False):
        voice = ctx.author.voice
        if not voice or not voice.channel:
            await ctx.send(view=ui.failure("You need to join a voice channel first."))
            return None
        player = ctx.voice_client
        if player and player.channel != voice.channel:
            await ctx.send(view=ui.failure(f"I am already in {player.channel.mention}."))
            return None
        if player is None:
            if not connect:
                await ctx.send(view=ui.failure("I am not connected to a voice channel."))
                return None
            if not wavelink.Pool.nodes:
                await ctx.send(view=ui.failure("The music node is not connected right now."))
                return None
            try:
                player = await voice.channel.connect(cls=wavelink.Player, self_deaf=True)
            except (discord.ClientException, asyncio.TimeoutError, wavelink.WavelinkException):
                await ctx.send(view=ui.failure("I could not join your voice channel."))
                return None
            await self.prepare(player, ctx.channel)
        player.home = ctx.channel
        return player

    async def active_player(self, ctx):
        player = ctx.voice_client
        if player is None:
            await ctx.send(view=ui.failure("I am not connected to a voice channel."))
            return None
        return player

    async def now_playing_payload(self, player, track):
        requester = mu.requester_id(track)
        if requester == self.bot.user.id:
            name = "Autoplay"
        else:
            member = player.guild.get_member(requester) if requester else None
            name = member.display_name if member else "Unknown"
        card = await mu.build_card(self.bot, track)
        view = mu.NowPlayingView(self.bot, player, track, name, card=card is not None)
        kwargs = {"view": view}
        if card:
            kwargs["file"] = card
        return kwargs

    async def queue_results(self, ctx, player, results):
        if isinstance(results, wavelink.Playlist):
            for track in results.tracks:
                mu.tag_requester(track, ctx.author.id)
            added = len(results.tracks)
            player.queue.put(results)
            return f"Added playlist **{clip(results.name, 100)}** with **{added}** tracks to the queue."
        track = results[0]
        mu.tag_requester(track, ctx.author.id)
        player.queue.put(track)
        return f"Added **{clip(track.title, 150)}** to the queue."

    async def start_if_idle(self, player):
        if not player.playing and not player.queue.is_empty:
            await player.play(player.queue.get())

    @commands.Cog.listener()
    async def on_ready(self):
        if self.restored:
            return
        self.restored = True
        rows = await self.bot.db.fetch(
            "SELECT guild_id, voice_id, text_id FROM guilds WHERE vc247 = 1 AND voice_id IS NOT NULL"
        )
        for row in rows:
            await self.rejoin(row["guild_id"], row["voice_id"], row["text_id"])

    async def rejoin(self, guild_id, voice_id, text_id):
        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(voice_id) if guild else None
        if channel is None or guild.voice_client is not None or not wavelink.Pool.nodes:
            return
        try:
            player = await channel.connect(cls=wavelink.Player, self_deaf=True)
            await self.prepare(player, guild.get_channel(text_id) if text_id else None)
        except Exception:
            log.warning("Could not restore 24/7 in guild %s", guild_id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id != self.bot.user.id or before.channel is None or after.channel is not None:
            return
        guild_id = before.channel.guild.id
        if guild_id in self.leaving:
            self.leaving.discard(guild_id)
            return
        row = await self.bot.db.one("SELECT vc247, voice_id, text_id FROM guilds WHERE guild_id = ?", guild_id)
        if row and row["vc247"] and row["voice_id"]:
            await asyncio.sleep(2)
            await self.rejoin(guild_id, row["voice_id"], row["text_id"])

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload):
        log.info("Lavalink node %s is ready", payload.node.identifier)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        player = payload.player
        if player is None:
            return
        track = payload.track
        if config.DELETE_OLD_NOW_PLAYING:
            await mu.delete_now_playing(player)
        home = getattr(player, "home", None)
        if home:
            try:
                kwargs = await self.now_playing_payload(player, track)
                player.np_message = await home.send(**kwargs)
            except discord.HTTPException:
                player.np_message = None
        text = config.VOICE_STATUS_TEXT.format(title=clip(track.title, 80))
        await mu.set_voice_status(self.bot, player.channel, text)
        requester = mu.requester_id(track) or 0
        await self.bot.db.run(
            "INSERT INTO song_plays (guild_id, user_id, uri, title, author, plays) VALUES (?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(guild_id, user_id, uri) DO UPDATE SET plays = plays + 1",
            player.guild.id,
            requester,
            track.uri or track.title,
            track.title,
            track.author,
        )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        player = payload.player
        if player is None:
            return
        await mu.delete_now_playing(player)
        if payload.reason != "finished":
            return
        if getattr(player, "xy_autoplay", False) and player.queue.is_empty and player.queue.mode == wavelink.QueueMode.normal:
            await asyncio.sleep(0.5)
            if player.queue.is_empty:
                await self.autoplay_next(player, payload.track)

    async def autoplay_next(self, player, last):
        try:
            results = await mu.search_tracks(self.bot, player.guild.id, f"{last.author} songs")
        except wavelink.WavelinkException:
            return
        if isinstance(results, wavelink.Playlist):
            results = results.tracks
        played = {track.uri for track in (player.queue.history or [])}
        choices = [track for track in results[: config.SEARCH_RESULTS] if track.uri not in played and track.uri != last.uri]
        if not choices:
            return
        track = random.choice(choices)
        mu.tag_requester(track, self.bot.user.id)
        await player.play(track)

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload):
        home = getattr(payload.player, "home", None)
        if home:
            await home.send(view=ui.failure(f"I could not play **{clip(payload.track.title, 100)}**."))

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player):
        keep = await self.bot.db.guild_value(player.guild.id, "vc247", 0)
        if keep:
            return
        await mu.delete_now_playing(player)
        await mu.set_voice_status(self.bot, player.channel, "")
        self.leaving.add(player.guild.id)
        await player.disconnect()

    @commands.hybrid_command(name="join", aliases=["connect"], description="Make the bot join your voice channel.")
    @commands.guild_only()
    async def join(self, ctx):
        player = await self.get_player(ctx, connect=True)
        if player:
            await ctx.send(view=ui.success(f"Joined {player.channel.mention}."))

    @commands.hybrid_command(name="disconnect", aliases=["dc", "leave"], description="Disconnect the bot from voice.")
    @commands.guild_only()
    async def disconnect(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        await mu.delete_now_playing(player)
        await mu.set_voice_status(self.bot, player.channel, "")
        self.leaving.add(ctx.guild.id)
        player.queue.clear()
        await player.disconnect()
        await ctx.send(view=ui.success("Disconnected from the voice channel."))

    @commands.hybrid_command(name="play", aliases=["p"], description="Play a song or add it to the queue.")
    @commands.guild_only()
    async def play(self, ctx, *, query: str):
        await ctx.defer()
        player = await self.get_player(ctx, connect=True)
        if not player:
            return
        if len(player.queue) >= config.MAX_QUEUE_SIZE:
            await ctx.send(view=ui.failure("The queue is full."))
            return
        try:
            results = await mu.search_tracks(self.bot, ctx.guild.id, query)
        except wavelink.WavelinkException:
            await ctx.send(view=ui.failure("I could not load that track."))
            return
        if not results:
            await ctx.send(view=ui.failure(f"No results were found for `{clip(query, 100)}`."))
            return
        body = await self.queue_results(ctx, player, results)
        await ctx.send(view=ui.success(body))
        await self.start_if_idle(player)

    @commands.hybrid_command(name="search", description="Search for a song and pick a result.")
    @commands.guild_only()
    async def search(self, ctx, *, query: str):
        await ctx.defer()
        if not ctx.author.voice:
            await ctx.send(view=ui.failure("You need to join a voice channel first."))
            return
        try:
            results = await mu.search_tracks(self.bot, ctx.guild.id, query)
        except wavelink.WavelinkException:
            await ctx.send(view=ui.failure("I could not search right now."))
            return
        if isinstance(results, wavelink.Playlist):
            results = results.tracks
        if not results:
            await ctx.send(view=ui.failure(f"No results were found for `{clip(query, 100)}`."))
            return
        tracks = list(results)[: config.SEARCH_RESULTS]

        async def pick(interaction, track):
            await interaction.response.defer()
            player = await self.get_player(ctx, connect=True)
            if not player:
                return
            body = await self.queue_results(ctx, player, [track])
            await interaction.followup.send(view=ui.success(body))
            await self.start_if_idle(player)

        await ui.send(ctx, mu.SearchView(ctx.author.id, tracks, pick))

    @commands.hybrid_command(name="pause", description="Pause the current track.")
    @commands.guild_only()
    async def pause(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        if player.paused:
            await ctx.send(view=ui.failure("The player is already paused."))
            return
        await player.pause(True)
        await ctx.send(view=ui.success("Paused the player."))

    @commands.hybrid_command(name="resume", aliases=["unpause"], description="Resume the current track.")
    @commands.guild_only()
    async def resume(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        if not player.paused:
            await ctx.send(view=ui.failure("The player is not paused."))
            return
        await player.pause(False)
        await ctx.send(view=ui.success("Resumed the player."))

    @commands.hybrid_command(name="skip", aliases=["s", "next"], description="Skip the current track.")
    @commands.guild_only()
    async def skip(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        if not player.current:
            await ctx.send(view=ui.failure("Nothing is playing right now."))
            return
        title = player.current.title
        await player.skip(force=True)
        await ctx.send(view=ui.success(f"Skipped **{clip(title, 150)}**."))

    @commands.hybrid_command(name="stop", description="Stop the player and clear the queue.")
    @commands.guild_only()
    async def stop(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        await mu.delete_now_playing(player)
        keep = await self.bot.db.guild_value(ctx.guild.id, "vc247", 0)
        if not keep:
            self.leaving.add(ctx.guild.id)
        await mu.stop_player(self.bot, player)
        await ctx.send(view=ui.success("Stopped the player and cleared the queue."))

    @commands.hybrid_command(name="volume", aliases=["vol"], description="Show or change the volume.")
    @commands.guild_only()
    async def volume(self, ctx, level: Optional[int] = None):
        player = await self.get_player(ctx)
        if not player:
            return
        if level is None:
            await ctx.send(view=ui.titled("MUSIC", "Volume", f"The current volume is `{player.volume}%`"))
            return
        if not 0 <= level <= config.MAX_VOLUME:
            await ctx.send(view=ui.failure(f"The volume must be between `0` and `{config.MAX_VOLUME}`."))
            return
        await player.set_volume(level)
        await self.bot.db.guild_set(ctx.guild.id, volume=level)
        await ctx.send(view=ui.success(f"Volume set to `{level}%`."))

    @commands.hybrid_command(name="loop", aliases=["repeat"], description="Set the loop mode.")
    @commands.guild_only()
    async def loop(self, ctx, mode: Optional[Literal["off", "track", "queue"]] = None):
        player = await self.get_player(ctx)
        if not player:
            return
        chosen = {
            "off": wavelink.QueueMode.normal,
            "track": wavelink.QueueMode.loop,
            "queue": wavelink.QueueMode.loop_all,
        }
        if mode is None:
            index = mu.LOOP_ORDER.index(player.queue.mode)
            target = mu.LOOP_ORDER[(index + 1) % len(mu.LOOP_ORDER)]
        else:
            target = chosen[mode]
        player.queue.mode = target
        await ctx.send(view=ui.success(f"Loop mode set to **{mu.LOOP_LABELS[target]}**."))

    @commands.hybrid_command(name="shuffle", description="Shuffle the queue.")
    @commands.guild_only()
    async def shuffle(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        if len(player.queue) < 2:
            await ctx.send(view=ui.failure("There are not enough tracks in the queue to shuffle."))
            return
        player.queue.shuffle()
        await ctx.send(view=ui.success("Shuffled the queue."))

    @commands.hybrid_command(name="seek", description="Seek to a position in the current track.")
    @commands.guild_only()
    async def seek(self, ctx, position: str):
        player = await self.get_player(ctx)
        if not player:
            return
        if not player.current:
            await ctx.send(view=ui.failure("Nothing is playing right now."))
            return
        target = parse_time(position)
        if target is None or target >= player.current.length:
            await ctx.send(view=ui.failure("Provide a valid time inside the track, like `1:30` or `90`."))
            return
        await player.seek(target)
        await ctx.send(view=ui.success(f"Seeked to `{fmt_duration(target)}`."))

    @commands.hybrid_command(name="replay", aliases=["restart"], description="Restart the current track.")
    @commands.guild_only()
    async def replay(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        if not player.current:
            await ctx.send(view=ui.failure("Nothing is playing right now."))
            return
        await player.seek(0)
        await ctx.send(view=ui.success("Restarted the current track."))

    @commands.hybrid_command(name="queue", aliases=["q"], description="Show the queue.")
    @commands.guild_only()
    async def queue(self, ctx):
        player = await self.active_player(ctx)
        if not player:
            return
        await ui.send(ctx, mu.QueueView(ctx.guild, player, ctx.author.id))

    @commands.hybrid_command(name="clearqueue", aliases=["cq", "clear"], description="Clear the queue.")
    @commands.guild_only()
    async def clearqueue(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        player.queue.clear()
        await ctx.send(view=ui.success("Cleared the queue."))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show the current track.")
    @commands.guild_only()
    async def nowplaying(self, ctx):
        player = await self.active_player(ctx)
        if not player:
            return
        if not player.current:
            await ctx.send(view=ui.failure("Nothing is playing right now."))
            return
        kwargs = await self.now_playing_payload(player, player.current)
        await ctx.send(**kwargs)

    @commands.hybrid_command(name="autoplay", description="Toggle autoplay.")
    @commands.guild_only()
    async def autoplay(self, ctx):
        enabled = not bool(await self.bot.db.guild_value(ctx.guild.id, "autoplay", 0))
        await self.bot.db.guild_set(ctx.guild.id, autoplay=int(enabled))
        if ctx.voice_client:
            ctx.voice_client.xy_autoplay = enabled
        state = "enabled" if enabled else "disabled"
        await ctx.send(view=ui.success(f"Autoplay has been **{state}**."))

    @commands.hybrid_command(name="engine", description="Choose the search engine.")
    @commands.guild_only()
    async def engine(self, ctx):
        current = await self.bot.db.guild_value(ctx.guild.id, "engine", config.DEFAULT_ENGINE)
        if current not in config.ENGINES:
            current = config.DEFAULT_ENGINE
        await ui.send(ctx, EngineView(self.bot, ctx.author, current))

    @commands.hybrid_command(name="filters", aliases=["filter"], description="Apply audio filters.")
    @commands.guild_only()
    async def filters(self, ctx):
        player = await self.get_player(ctx)
        if not player:
            return
        await ui.send(ctx, mu.FiltersView(self.bot, player, ctx.author.id))

    @commands.hybrid_group(name="247", description="Keep the bot in voice 24/7.", invoke_without_command=True)
    @commands.guild_only()
    async def twentyfour(self, ctx):
        row = await self.bot.db.one("SELECT vc247, voice_id, text_id FROM guilds WHERE guild_id = ?", ctx.guild.id)
        enabled = bool(row and row["vc247"])
        voice_id = row["voice_id"] if row and row["voice_id"] else (ctx.author.voice.channel.id if ctx.author.voice else None)
        text_id = row["text_id"] if row and row["text_id"] else ctx.channel.id
        prefix = ctx.clean_prefix
        title = "24/7 Mode Enabled" if enabled else "24/7 Mode Disabled"
        icon = "SUCCESS" if enabled else "ERROR"
        details = quote(
            f"{E('DOT')} **Status:** `{'Enabled' if enabled else 'Disabled'}`",
            f"{E('DOT')} **Text Channel:** {f'<#{text_id}>' if text_id else '`Not set`'}",
            f"{E('DOT')} **Voice Channel:** {f'<#{voice_id}>' if voice_id else '`Not set`'}",
        )
        body = f"{details}\n\n-# Usage: `{prefix}247 activate` or `{prefix}247 deactivate`."
        await ctx.send(view=ui.titled(icon, title, body))

    @twentyfour.command(name="activate", description="Enable 24/7 mode.")
    @commands.has_permissions(manage_guild=True)
    async def activate(self, ctx):
        player = await self.get_player(ctx, connect=True)
        if not player:
            return
        await self.bot.db.guild_set(ctx.guild.id, vc247=1, voice_id=player.channel.id, text_id=ctx.channel.id)
        player.inactive_timeout = None
        await ctx.send(view=ui.success(f"24/7 mode is now enabled in {player.channel.mention}.", title="24/7 Mode Enabled"))

    @twentyfour.command(name="deactivate", description="Disable 24/7 mode.")
    @commands.has_permissions(manage_guild=True)
    async def deactivate(self, ctx):
        await self.bot.db.guild_set(ctx.guild.id, vc247=0)
        if ctx.voice_client:
            ctx.voice_client.inactive_timeout = config.INACTIVE_TIMEOUT
        await ctx.send(view=ui.success("24/7 mode has been disabled."))

    async def resolve_uri(self, uri):
        try:
            results = await wavelink.Playable.search(uri)
        except wavelink.WavelinkException:
            return None
        if isinstance(results, wavelink.Playlist):
            results = results.tracks
        return results[0] if results else None

    async def queue_saved(self, ctx, rows, label):
        await ctx.defer()
        if not rows:
            await ctx.send(view=ui.failure("There are no saved tracks to play."))
            return
        player = await self.get_player(ctx, connect=True)
        if not player:
            return
        gate = asyncio.Semaphore(5)

        async def load(row):
            async with gate:
                return await self.resolve_uri(row["uri"])

        tracks = [track for track in await asyncio.gather(*[load(row) for row in rows]) if track]
        if not tracks:
            await ctx.send(view=ui.failure("None of the saved tracks could be loaded."))
            return
        for track in tracks:
            mu.tag_requester(track, ctx.author.id)
            player.queue.put(track)
        await ctx.send(view=ui.success(f"Added **{len(tracks)}** tracks from {label} to the queue."))
        await self.start_if_idle(player)

    @commands.hybrid_group(name="liked", description="Manage your liked songs.", invoke_without_command=True)
    async def liked(self, ctx):
        rows = await self.bot.db.fetch(
            "SELECT uri, title, length FROM liked WHERE user_id = ? ORDER BY added DESC", ctx.author.id
        )
        prefix = ctx.clean_prefix
        if rows:
            lines = "\n".join(
                f"`{index + 1}.` [{clip(row['title'], 60)}]({row['uri']}) • `{fmt_duration(row['length'])}`"
                for index, row in enumerate(rows[:15])
            )
        else:
            lines = quote("You have not liked any songs yet.")
        footer = f"-# {len(rows)} liked songs • {prefix}liked add | remove | play | clear"
        await ctx.send(view=ui.plain(f"# {E('MUSIC')} Liked Songs\n{lines}\n{footer}"))

    @liked.command(name="add", description="Like the current track.")
    @commands.guild_only()
    async def liked_add(self, ctx):
        player = ctx.voice_client
        if not player or not player.current:
            await ctx.send(view=ui.failure("Nothing is playing right now."))
            return
        total = await self.bot.db.scalar("SELECT COUNT(*) FROM liked WHERE user_id = ?", ctx.author.id, default=0)
        if total >= config.MAX_LIKED:
            await ctx.send(view=ui.failure("Your liked songs list is full."))
            return
        track = player.current
        await self.bot.db.run(
            "INSERT OR REPLACE INTO liked (user_id, uri, title, author, length, added) VALUES (?, ?, ?, ?, ?, ?)",
            ctx.author.id,
            track.uri,
            track.title,
            track.author,
            track.length,
            now(),
        )
        await ctx.send(view=ui.success(f"Added **{clip(track.title, 120)}** to your liked songs."))

    @liked.command(name="remove", description="Remove a liked song by its number.")
    async def liked_remove(self, ctx, number: int):
        rows = await self.bot.db.fetch(
            "SELECT uri, title FROM liked WHERE user_id = ? ORDER BY added DESC", ctx.author.id
        )
        if not 1 <= number <= len(rows):
            await ctx.send(view=ui.failure("Provide a valid song number from your liked list."))
            return
        row = rows[number - 1]
        await self.bot.db.run("DELETE FROM liked WHERE user_id = ? AND uri = ?", ctx.author.id, row["uri"])
        await ctx.send(view=ui.success(f"Removed **{clip(row['title'], 120)}** from your liked songs."))

    @liked.command(name="play", description="Queue all your liked songs.")
    @commands.guild_only()
    async def liked_play(self, ctx):
        rows = await self.bot.db.fetch(
            "SELECT uri FROM liked WHERE user_id = ? ORDER BY added DESC LIMIT ?",
            ctx.author.id,
            config.MAX_PLAYLIST_TRACKS,
        )
        await self.queue_saved(ctx, rows, "your liked songs")

    @liked.command(name="clear", description="Remove all liked songs.")
    async def liked_clear(self, ctx):
        await self.bot.db.run("DELETE FROM liked WHERE user_id = ?", ctx.author.id)
        await ctx.send(view=ui.success("Cleared your liked songs."))

    async def playlist_row(self, ctx, name):
        row = await self.bot.db.one(
            "SELECT id, name FROM playlists WHERE user_id = ? AND LOWER(name) = LOWER(?)", ctx.author.id, name
        )
        if row is None:
            await ctx.send(view=ui.failure(f"You do not have a playlist named `{clip(name, 50)}`."))
        return row

    @commands.hybrid_group(name="playlist", aliases=["pl"], description="Manage your playlists.", invoke_without_command=True)
    async def playlist(self, ctx):
        rows = await self.bot.db.fetch(
            "SELECT p.name, COUNT(t.id) AS total FROM playlists p LEFT JOIN playlist_tracks t ON t.playlist_id = p.id "
            "WHERE p.user_id = ? GROUP BY p.id ORDER BY p.name",
            ctx.author.id,
        )
        prefix = ctx.clean_prefix
        if rows:
            lines = "\n".join(f"{E('DOT')} **{clip(row['name'], 40)}** • `{row['total']}` tracks" for row in rows)
        else:
            lines = quote("You do not have any playlists yet.")
        usage = f"-# {prefix}playlist create | add | remove | view | play | delete"
        await ctx.send(view=ui.plain(f"# {E('MUSIC')} Your Playlists\n{lines}\n{usage}"))

    @playlist.command(name="create", description="Create a playlist.")
    async def playlist_create(self, ctx, *, name: str):
        total = await self.bot.db.scalar("SELECT COUNT(*) FROM playlists WHERE user_id = ?", ctx.author.id, default=0)
        if total >= config.MAX_PLAYLISTS:
            await ctx.send(view=ui.failure(f"You can only have **{config.MAX_PLAYLISTS}** playlists."))
            return
        name = clip(name.strip(), 40)
        exists = await self.bot.db.scalar(
            "SELECT 1 FROM playlists WHERE user_id = ? AND LOWER(name) = LOWER(?)", ctx.author.id, name
        )
        if exists:
            await ctx.send(view=ui.failure("You already have a playlist with that name."))
            return
        await self.bot.db.run("INSERT INTO playlists (user_id, name) VALUES (?, ?)", ctx.author.id, name)
        await ctx.send(view=ui.success(f"Created the playlist **{name}**."))

    @playlist.command(name="add", description="Add the current track or a search to a playlist.")
    async def playlist_add(self, ctx, name: str, *, query: Optional[str] = None):
        row = await self.playlist_row(ctx, name)
        if row is None:
            return
        count = await self.bot.db.scalar(
            "SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?", row["id"], default=0
        )
        if count >= config.MAX_PLAYLIST_TRACKS:
            await ctx.send(view=ui.failure("That playlist is full."))
            return
        if query:
            try:
                results = await mu.search_tracks(self.bot, ctx.guild.id if ctx.guild else 0, query)
            except wavelink.WavelinkException:
                await ctx.send(view=ui.failure("I could not load that track."))
                return
            if isinstance(results, wavelink.Playlist):
                results = results.tracks
            track = results[0] if results else None
        else:
            track = ctx.voice_client.current if ctx.voice_client else None
        if track is None:
            await ctx.send(view=ui.failure("Provide a song to add or play one first."))
            return
        await self.bot.db.run(
            "INSERT INTO playlist_tracks (playlist_id, uri, title, author, length) VALUES (?, ?, ?, ?, ?)",
            row["id"],
            track.uri,
            track.title,
            track.author,
            track.length,
        )
        await ctx.send(view=ui.success(f"Added **{clip(track.title, 100)}** to **{row['name']}**."))

    @playlist.command(name="remove", description="Remove a track from a playlist.")
    async def playlist_remove(self, ctx, name: str, number: int):
        row = await self.playlist_row(ctx, name)
        if row is None:
            return
        tracks = await self.bot.db.fetch(
            "SELECT id, title FROM playlist_tracks WHERE playlist_id = ? ORDER BY id", row["id"]
        )
        if not 1 <= number <= len(tracks):
            await ctx.send(view=ui.failure("Provide a valid track number."))
            return
        await self.bot.db.run("DELETE FROM playlist_tracks WHERE id = ?", tracks[number - 1]["id"])
        await ctx.send(view=ui.success(f"Removed **{clip(tracks[number - 1]['title'], 100)}** from **{row['name']}**."))

    @playlist.command(name="view", description="View the tracks in a playlist.")
    async def playlist_view(self, ctx, *, name: str):
        row = await self.playlist_row(ctx, name)
        if row is None:
            return
        tracks = await self.bot.db.fetch(
            "SELECT uri, title, length FROM playlist_tracks WHERE playlist_id = ? ORDER BY id LIMIT 20", row["id"]
        )
        if tracks:
            lines = "\n".join(
                f"`{index + 1}.` [{clip(item['title'], 60)}]({item['uri']}) • `{fmt_duration(item['length'])}`"
                for index, item in enumerate(tracks)
            )
        else:
            lines = quote("This playlist is empty.")
        await ctx.send(view=ui.plain(f"# {E('MUSIC')} {row['name']}\n{lines}"))

    @playlist.command(name="play", description="Queue a playlist.")
    @commands.guild_only()
    async def playlist_play(self, ctx, *, name: str):
        row = await self.playlist_row(ctx, name)
        if row is None:
            return
        tracks = await self.bot.db.fetch(
            "SELECT uri FROM playlist_tracks WHERE playlist_id = ? ORDER BY id", row["id"]
        )
        await self.queue_saved(ctx, tracks, f"**{row['name']}**")

    @playlist.command(name="delete", description="Delete a playlist.")
    async def playlist_delete(self, ctx, *, name: str):
        row = await self.playlist_row(ctx, name)
        if row is None:
            return
        await self.bot.db.run("DELETE FROM playlist_tracks WHERE playlist_id = ?", row["id"])
        await self.bot.db.run("DELETE FROM playlists WHERE id = ?", row["id"])
        await ctx.send(view=ui.success(f"Deleted the playlist **{row['name']}**."))

    @commands.hybrid_command(name="songstats", description="Show music statistics for this server.")
    @commands.guild_only()
    async def songstats(self, ctx):
        db = self.bot.db
        total = await db.scalar("SELECT SUM(plays) FROM song_plays WHERE guild_id = ?", ctx.guild.id, default=0)
        mine = await db.scalar(
            "SELECT SUM(plays) FROM song_plays WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id, default=0
        )
        tracks = await db.fetch(
            "SELECT title, SUM(plays) AS total FROM song_plays WHERE guild_id = ? GROUP BY uri "
            "ORDER BY total DESC LIMIT ?",
            ctx.guild.id,
            config.SONG_STATS_TOP,
        )
        listeners = await db.fetch(
            "SELECT user_id, SUM(plays) AS total FROM song_plays WHERE guild_id = ? AND user_id != 0 "
            "GROUP BY user_id ORDER BY total DESC LIMIT ?",
            ctx.guild.id,
            config.SONG_STATS_TOP,
        )
        top_tracks = "\n".join(
            f"`{index + 1}.` {clip(row['title'], 60)} • `{row['total']}` plays" for index, row in enumerate(tracks)
        ) or "`No data yet`"
        top_users = "\n".join(
            f"`{index + 1}.` <@{row['user_id']}> • `{row['total']}` plays" for index, row in enumerate(listeners)
        ) or "`No data yet`"
        body = (
            f"# {E('MUSIC')} Song Stats\n"
            + quote(
                f"{E('DOT')} **Server Plays:** `{total}`",
                f"{E('DOT')} **Your Requests:** `{mine}`",
            )
            + f"\n### Top Tracks\n{top_tracks}\n### Top Listeners\n{top_users}"
        )
        await ctx.send(view=ui.plain(body))

    @commands.hybrid_command(name="artist", description="Queue top songs of an artist.")
    @commands.guild_only()
    async def artist(self, ctx, *, name: str):
        await ctx.defer()
        player = await self.get_player(ctx, connect=True)
        if not player:
            return
        try:
            results = await mu.search_tracks(self.bot, ctx.guild.id, f"{name} top songs")
        except wavelink.WavelinkException:
            await ctx.send(view=ui.failure("I could not search right now."))
            return
        if isinstance(results, wavelink.Playlist):
            results = results.tracks
        results = list(results)
        matched = [track for track in results if name.lower() in track.author.lower()] or results
        picked = matched[: config.ARTIST_TRACKS]
        if not picked:
            await ctx.send(view=ui.failure(f"No songs were found for `{clip(name, 100)}`."))
            return
        for track in picked:
            mu.tag_requester(track, ctx.author.id)
            player.queue.put(track)
        await ctx.send(view=ui.success(f"Added **{len(picked)}** tracks by **{clip(name, 80)}** to the queue."))
        await self.start_if_idle(player)


async def setup(bot):
    await bot.add_cog(Music(bot))
