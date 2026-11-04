import re
from typing import Optional

import discord
from discord.ext import commands

import config
from utils import ui
from utils.emojis import E
from utils.helpers import apply_variables, clip, quote

IMAGE_COLUMNS = ("author_icon", "footer_icon", "thumbnail", "image")
VARIABLE_VALUES = {"{user_avatar}", "{server_icon}"}


def render_welcome(row, member):
    defaults = config.WELCOME_DEFAULTS
    title = apply_variables(row["title"] or defaults["title"], member)
    description = apply_variables(row["description"] or defaults["description"], member)
    colour = int((row["color"] or defaults["color"]).lstrip("#"), 16)
    embed = discord.Embed(title=clip(title, 256), description=clip(description, 4000), colour=colour)

    def url(value):
        resolved = apply_variables(value, member) if value else None
        return resolved if resolved and resolved.startswith("http") else None

    if row["author_name"]:
        embed.set_author(name=clip(apply_variables(row["author_name"], member), 256), icon_url=url(row["author_icon"]))
    if row["footer_text"]:
        embed.set_footer(text=clip(apply_variables(row["footer_text"], member), 2048), icon_url=url(row["footer_icon"]))
    if url(row["thumbnail"]):
        embed.set_thumbnail(url=url(row["thumbnail"]))
    if url(row["image"]):
        embed.set_image(url=url(row["image"]))
    content = apply_variables(row["message"], member) if row["message"] else None
    return content, embed


def validate(values):
    color = values.get("color")
    if color and not re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
        return "The color must be a hex value like `D9B99B`."
    if "color" in values and color:
        values["color"] = color.lstrip("#").upper()
    if "autodelete" in values:
        raw = values["autodelete"]
        if raw is None:
            values["autodelete"] = 0
        elif not raw.isdigit() or int(raw) > 600:
            return "Auto-delete must be a number between `0` and `600` seconds."
        else:
            values["autodelete"] = int(raw)
    for column in IMAGE_COLUMNS:
        value = values.get(column)
        if value and not (value.startswith("http") or value in VARIABLE_VALUES):
            return "Image values must be a link or one of `{user_avatar}` and `{server_icon}`."
    return None


class FieldModal(discord.ui.Modal):
    def __init__(self, title, fields, row, on_done):
        super().__init__(title=title)
        self.on_done = on_done
        self.inputs = {}
        for column, label, style, required, limit in fields:
            current = row[column] if row is not None and row[column] is not None else None
            item = discord.ui.TextInput(
                label=label,
                style=style,
                required=required,
                max_length=limit,
                default=str(current) if current is not None else None,
            )
            self.inputs[column] = item
            self.add_item(item)

    async def on_submit(self, interaction):
        values = {column: (item.value.strip() or None) for column, item in self.inputs.items()}
        error = validate(values)
        if error:
            await interaction.response.send_message(view=ui.failure(error), ephemeral=True)
            return
        await self.on_done(interaction, values)


class ChannelPicker(discord.ui.View):
    def __init__(self, author_id, on_pick):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.on_pick = on_pick
        picker = discord.ui.ChannelSelect(
            placeholder="Select the welcome channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )
        picker.callback = self.picked
        self.picker = picker
        self.add_item(picker)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id

    async def picked(self, interaction):
        await self.on_pick(interaction, self.picker.values[0].id)


SHORT = discord.TextStyle.short
LONG = discord.TextStyle.paragraph

BASIC_FIELDS = [
    ("title", "Title", SHORT, False, 256),
    ("description", "Description", LONG, False, 2000),
    ("color", "Embed color (hex)", SHORT, False, 7),
    ("autodelete", "Auto-delete after (seconds)", SHORT, False, 3),
]
AUTHOR_FIELDS = [
    ("author_name", "Author name", SHORT, False, 256),
    ("author_icon", "Author icon (link or variable)", SHORT, False, 500),
]
FOOTER_FIELDS = [
    ("footer_text", "Footer text", SHORT, False, 500),
    ("footer_icon", "Footer icon (link or variable)", SHORT, False, 500),
]
IMAGE_FIELDS = [
    ("thumbnail", "Thumbnail (link or variable)", SHORT, False, 500),
    ("image", "Large image (link or variable)", SHORT, False, 500),
]
MESSAGE_FIELDS = [("message", "Message above the embed", LONG, False, 1500)]


class WelcomeView(ui.BaseView):
    def __init__(self, bot, author, guild):
        super().__init__(author_id=author.id)
        self.bot = bot
        self.author = author
        self.guild = guild
        self.row = None

    async def load(self):
        await self.bot.db.run("INSERT OR IGNORE INTO welcome (guild_id) VALUES (?)", self.guild.id)
        self.row = await self.bot.db.one("SELECT * FROM welcome WHERE guild_id = ?", self.guild.id)
        self.clear_items()
        self.add_item(self.build())
        return self

    async def update(self, **columns):
        names = ", ".join(f"{name} = ?" for name in columns)
        await self.bot.db.run(f"UPDATE welcome SET {names} WHERE guild_id = ?", *columns.values(), self.guild.id)

    def build(self):
        row = self.row
        enabled = bool(row["enabled"])
        channel = f"<#{row['channel_id']}>" if row["channel_id"] else "`Not set`"
        status = f"{E('SUCCESS')} **Enabled**" if enabled else f"{E('ERROR')} **Disabled**"
        variables = " • ".join(f"`{name}`" for name in config.WELCOME_VARIABLES)
        body = (
            f"# {E('CONFIG')} {config.BOT_NAME} Welcome Setup\n"
            f"Configure a professional welcome message for **{self.guild.name}** from this panel.\n\n"
            + quote(
                f"**Status:** {status}",
                f"**Channel:** {channel}",
                f"**Auto-delete:** `{row['autodelete']}s`",
            )
            + "\n### Welcome Editor\n"
            "Use the buttons below to configure the message, images, author and footer.\n\n"
            f"**Variables:** {variables}"
        )
        primary = discord.ButtonStyle.primary
        return ui.box(
            ui.text(body),
            ui.row(
                ui.button("Edit Basic", callback=self.edit_basic),
                ui.button("Edit Author", callback=self.edit_author),
                ui.button("Edit Footer", callback=self.edit_footer),
            ),
            ui.row(
                ui.button("Edit Images", callback=self.edit_images),
                ui.button("Set Channel", style=primary, callback=self.set_channel),
            ),
            ui.row(
                ui.button(
                    "Disable" if enabled else "Enable",
                    style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success,
                    callback=self.toggle,
                ),
                ui.button("Test Welcome", callback=self.test),
                ui.button("Set Message", callback=self.set_message),
            ),
            ui.row(
                ui.button("Reset", style=discord.ButtonStyle.danger, callback=self.reset),
                ui.link("Need Help? Support", config.SUPPORT_URL),
            ),
        )

    async def refresh(self, interaction):
        await self.load()
        await interaction.response.edit_message(view=self)

    def opener(self, title, fields):
        async def callback(interaction):
            async def done(modal_interaction, values):
                await self.update(**values)
                await self.refresh(modal_interaction)

            await interaction.response.send_modal(FieldModal(title, fields, self.row, done))

        return callback

    async def edit_basic(self, interaction):
        await self.opener("Edit Basic", BASIC_FIELDS)(interaction)

    async def edit_author(self, interaction):
        await self.opener("Edit Author", AUTHOR_FIELDS)(interaction)

    async def edit_footer(self, interaction):
        await self.opener("Edit Footer", FOOTER_FIELDS)(interaction)

    async def edit_images(self, interaction):
        await self.opener("Edit Images", IMAGE_FIELDS)(interaction)

    async def set_message(self, interaction):
        await self.opener("Set Message", MESSAGE_FIELDS)(interaction)

    async def set_channel(self, interaction):
        async def picked(picker_interaction, channel_id):
            await self.update(channel_id=channel_id)
            await picker_interaction.response.edit_message(content=f"Welcome channel set to <#{channel_id}>.", view=None)
            await self.load()
            if self.message:
                await self.message.edit(view=self)

        await interaction.response.send_message(view=ChannelPicker(interaction.user.id, picked), ephemeral=True)

    async def toggle(self, interaction):
        if not self.row["enabled"] and not self.row["channel_id"]:
            await interaction.response.send_message(view=ui.failure("Set a welcome channel first."), ephemeral=True)
            return
        await self.update(enabled=0 if self.row["enabled"] else 1)
        await self.refresh(interaction)

    async def test(self, interaction):
        content, embed = render_welcome(self.row, interaction.user)
        await interaction.response.send_message(content=content, embed=embed, ephemeral=True)

    async def reset(self, interaction):
        await self.bot.db.run("DELETE FROM welcome WHERE guild_id = ?", self.guild.id)
        await self.refresh(interaction)


class Settings(commands.Cog):
    category = "config"

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        row = await self.bot.db.one("SELECT * FROM welcome WHERE guild_id = ?", member.guild.id)
        if not row or not row["enabled"] or not row["channel_id"]:
            return
        channel = member.guild.get_channel(row["channel_id"])
        if channel is None:
            return
        content, embed = render_welcome(row, member)
        try:
            await channel.send(content=content, embed=embed, delete_after=row["autodelete"] or None)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or self.bot.message_ignored(message):
            return
        content = message.content.lower()
        if not content:
            return
        guild_id = message.guild.id

        def found(trigger):
            return re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", content) is not None

        for trigger, reaction in self.bot.reacts.get(guild_id, {}).items():
            if found(trigger):
                try:
                    await message.add_reaction(reaction)
                except discord.HTTPException:
                    pass
        for trigger, response in self.bot.responds.get(guild_id, {}).items():
            if found(trigger):
                try:
                    await message.reply(response, mention_author=False)
                except discord.HTTPException:
                    pass
                break

    @commands.hybrid_command(name="greet", aliases=["welcome"], description="Configure the welcome message.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def greet(self, ctx):
        view = WelcomeView(self.bot, ctx.author, ctx.guild)
        await view.load()
        await ui.send(ctx, view)

    @commands.hybrid_group(name="ignore", description="Manage ignored channels and users.", invoke_without_command=True)
    @commands.guild_only()
    async def ignore(self, ctx):
        await ctx.send(
            view=ui.titled("ERROR", f"{config.BOT_NAME} Ignore", "Invalid subcommand. Use `add`, `remove`, or `list`.")
        )

    @ignore.command(name="add", description="Ignore a channel or a user.")
    @commands.has_permissions(manage_guild=True)
    async def ignore_add(self, ctx, channel: Optional[discord.TextChannel] = None, user: Optional[discord.Member] = None):
        target = channel or user
        if target is None:
            await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}ignore add <#channel|@user>"))
            return
        kind = "channel" if channel else "user"
        await self.bot.db.run(
            "INSERT OR REPLACE INTO ignores (guild_id, target_id, kind) VALUES (?, ?, ?)", ctx.guild.id, target.id, kind
        )
        self.bot.ignored.setdefault(ctx.guild.id, set()).add(target.id)
        await ctx.send(view=ui.success(f"{target.mention} is now ignored.", title=f"{config.BOT_NAME} Ignore"))

    @ignore.command(name="remove", description="Stop ignoring a channel or a user.")
    @commands.has_permissions(manage_guild=True)
    async def ignore_remove(self, ctx, channel: Optional[discord.TextChannel] = None, user: Optional[discord.Member] = None):
        target = channel or user
        if target is None:
            await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}ignore remove <#channel|@user>"))
            return
        await self.bot.db.run("DELETE FROM ignores WHERE guild_id = ? AND target_id = ?", ctx.guild.id, target.id)
        self.bot.ignored.get(ctx.guild.id, set()).discard(target.id)
        await ctx.send(view=ui.success(f"{target.mention} is no longer ignored.", title=f"{config.BOT_NAME} Ignore"))

    @ignore.command(name="list", description="List ignored channels and users.")
    async def ignore_list(self, ctx):
        rows = await self.bot.db.fetch(
            "SELECT target_id, kind FROM ignores WHERE guild_id = ? LIMIT ?", ctx.guild.id, config.IGNORE_LIST_LIMIT
        )
        channels = [f"<#{row['target_id']}>" for row in rows if row["kind"] == "channel"]
        users = [f"<@{row['target_id']}>" for row in rows if row["kind"] == "user"]
        body = (
            f"**Channels:** {', '.join(channels) if channels else '`None`'}\n"
            f"**Users:** {', '.join(users) if users else '`None`'}"
        )
        await ctx.send(view=ui.titled("CONFIG", f"{config.BOT_NAME} Ignore", body))

    def manager_view(self, name, noun, lines):
        prefix_lines = quote(*lines)
        body = (
            f"# {name} Manager\n## {E('CONFIG')} {name} Manager\n"
            f"{quote(f'Manage {noun} for this server.')}\n\n"
            f"**Commands**\n{prefix_lines}\n\n-# Admin only • Server configuration"
        )
        return ui.plain(body)

    @commands.hybrid_group(name="react", description="Manage auto-reactions.", invoke_without_command=True)
    @commands.guild_only()
    async def react(self, ctx):
        prefix = ctx.clean_prefix
        lines = [
            f"`{prefix}react add <trigger> <reaction>` — Add an auto-reaction.",
            f"`{prefix}react remove <trigger>` — Remove a auto-reaction.",
            f"`{prefix}react list` — View all configured auto-reactions.",
        ]
        await ctx.send(view=self.manager_view("Auto-React", "auto-reactions", lines))

    @react.command(name="add", description="Add an auto-reaction.")
    @commands.has_permissions(manage_guild=True)
    async def react_add(self, ctx, trigger: str, reaction: str):
        store = self.bot.reacts.setdefault(ctx.guild.id, {})
        trigger = trigger.lower()
        if trigger not in store and len(store) >= config.AUTO_RESPONSE_LIMIT:
            await ctx.send(view=ui.failure(f"You can only have **{config.AUTO_RESPONSE_LIMIT}** auto-reactions."))
            return
        store[trigger] = reaction
        await self.bot.db.run(
            "INSERT OR REPLACE INTO reacts (guild_id, trigger, reaction) VALUES (?, ?, ?)", ctx.guild.id, trigger, reaction
        )
        await ctx.send(view=ui.success(f"I will react with {reaction} to `{clip(trigger, 50)}`."))

    @react.command(name="remove", description="Remove an auto-reaction.")
    @commands.has_permissions(manage_guild=True)
    async def react_remove(self, ctx, trigger: str):
        trigger = trigger.lower()
        if trigger not in self.bot.reacts.get(ctx.guild.id, {}):
            await ctx.send(view=ui.failure("That trigger does not exist."))
            return
        del self.bot.reacts[ctx.guild.id][trigger]
        await self.bot.db.run("DELETE FROM reacts WHERE guild_id = ? AND trigger = ?", ctx.guild.id, trigger)
        await ctx.send(view=ui.success(f"Removed the auto-reaction for `{clip(trigger, 50)}`."))

    @react.command(name="list", description="List auto-reactions.")
    async def react_list(self, ctx):
        store = self.bot.reacts.get(ctx.guild.id, {})
        body = "\n".join(f"`{clip(key, 40)}` → {value}" for key, value in store.items()) or "`None configured`"
        await ctx.send(view=ui.titled("CONFIG", "Auto-Reactions", body))

    @commands.hybrid_group(name="respond", description="Manage auto-responses.", invoke_without_command=True)
    @commands.guild_only()
    async def respond(self, ctx):
        prefix = ctx.clean_prefix
        lines = [
            f"`{prefix}respond add <trigger> <response>` — Add an auto-response.",
            f"`{prefix}respond remove <trigger>` — Remove a auto-response.",
            f"`{prefix}respond list` — View all configured auto-responses.",
        ]
        await ctx.send(view=self.manager_view("Auto-Respond", "auto-responses", lines))

    @respond.command(name="add", description="Add an auto-response.")
    @commands.has_permissions(manage_guild=True)
    async def respond_add(self, ctx, trigger: str, *, response: str):
        store = self.bot.responds.setdefault(ctx.guild.id, {})
        trigger = trigger.lower()
        if trigger not in store and len(store) >= config.AUTO_RESPONSE_LIMIT:
            await ctx.send(view=ui.failure(f"You can only have **{config.AUTO_RESPONSE_LIMIT}** auto-responses."))
            return
        response = clip(response, 1500)
        store[trigger] = response
        await self.bot.db.run(
            "INSERT OR REPLACE INTO responds (guild_id, trigger, response) VALUES (?, ?, ?)", ctx.guild.id, trigger, response
        )
        await ctx.send(view=ui.success(f"I will respond to `{clip(trigger, 50)}`."))

    @respond.command(name="remove", description="Remove an auto-response.")
    @commands.has_permissions(manage_guild=True)
    async def respond_remove(self, ctx, trigger: str):
        trigger = trigger.lower()
        if trigger not in self.bot.responds.get(ctx.guild.id, {}):
            await ctx.send(view=ui.failure("That trigger does not exist."))
            return
        del self.bot.responds[ctx.guild.id][trigger]
        await self.bot.db.run("DELETE FROM responds WHERE guild_id = ? AND trigger = ?", ctx.guild.id, trigger)
        await ctx.send(view=ui.success(f"Removed the auto-response for `{clip(trigger, 50)}`."))

    @respond.command(name="list", description="List auto-responses.")
    async def respond_list(self, ctx):
        store = self.bot.responds.get(ctx.guild.id, {})
        body = "\n".join(f"`{clip(key, 40)}` → {clip(value, 80)}" for key, value in store.items()) or "`None configured`"
        await ctx.send(view=ui.titled("CONFIG", "Auto-Responses", body))


async def setup(bot):
    await bot.add_cog(Settings(bot))
