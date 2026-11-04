from typing import Optional

import discord
from discord.ext import commands

import config
from utils import ui
from utils.emojis import E
from utils.helpers import apply_variables, clip, now, number, quote


class PingsView(ui.BaseView):
    def __init__(self, bot, member):
        super().__init__(author_id=member.id)
        self.bot = bot
        self.member = member
        self.add_item(
            ui.box(
                ui.text(f"{E('AFK')} **Welcome Back**"),
                ui.sep(),
                ui.text(f"Welcome back, {member.mention}! Your AFK status has been removed."),
                ui.row(ui.button(label="Pings", callback=self.on_pings)),
            )
        )

    async def on_pings(self, interaction):
        rows = await self.bot.db.fetch(
            "SELECT author_id, channel_id, message_id, content FROM afk_pings "
            "WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
            interaction.guild_id,
            self.member.id,
            config.AFK_PING_LIMIT,
        )
        await self.bot.db.run(
            "DELETE FROM afk_pings WHERE guild_id = ? AND user_id = ?", interaction.guild_id, self.member.id
        )
        if rows:
            lines = [
                f"<@{row['author_id']}> in <#{row['channel_id']}>: {clip(row['content'], 120)} "
                f"([jump](https://discord.com/channels/{interaction.guild_id}/{row['channel_id']}/{row['message_id']}))"
                for row in rows
            ]
            body = "\n".join(lines)
        else:
            body = "No pings or replies were recorded while you were AFK."
        view = ui.layout(
            ui.box(ui.text(f"# {E('AFK')} AFK Pings"), ui.sep(), ui.text(f"**{self.member.name}**\n\n{body}"))
        )
        await interaction.response.send_message(view=view, ephemeral=True)


class Utility(commands.Cog):
    category = "utility"

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or self.bot.message_ignored(message):
            return
        key = (message.guild.id, message.author.id)
        entry = self.bot.afk.get(key)
        if entry and entry["mid"] != message.id:
            self.bot.afk.pop(key, None)
            await self.bot.db.run(
                "DELETE FROM afk WHERE guild_id = ? AND user_id = ?", message.guild.id, message.author.id
            )
            view = PingsView(self.bot, message.author)
            sent = await message.reply(view=view)
            view.message = sent
        for member in message.mentions:
            target = self.bot.afk.get((message.guild.id, member.id))
            if not target or member.id == message.author.id:
                continue
            await self.bot.db.run(
                "INSERT INTO afk_pings (guild_id, user_id, author_id, channel_id, message_id, content, created) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                message.guild.id,
                member.id,
                message.author.id,
                message.channel.id,
                message.id,
                message.content,
                now(),
            )
            await message.reply(
                view=ui.plain(
                    f"{E('AFK')} **{member.display_name}** is AFK: {clip(target['reason'], 200)} • <t:{target['since']}:R>"
                )
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        template = await self.bot.db.guild_value(member.guild.id, "joinmsg")
        if not template:
            return
        try:
            await member.send(apply_variables(template, member))
        except discord.HTTPException:
            pass

    @commands.hybrid_command(name="afk", description="Set your AFK status.")
    @commands.guild_only()
    async def afk(self, ctx, *, reason: str = "AFK"):
        reason = clip(reason, 200)
        since = now()
        message_id = ctx.message.id if ctx.interaction is None else 0
        self.bot.afk[(ctx.guild.id, ctx.author.id)] = {"reason": reason, "since": since, "mid": message_id}
        await self.bot.db.run(
            "INSERT OR REPLACE INTO afk (guild_id, user_id, reason, since) VALUES (?, ?, ?, ?)",
            ctx.guild.id,
            ctx.author.id,
            reason,
            since,
        )
        body = (
            f"{ctx.author.mention} is now AFK.\n"
            f"**Username:** `{ctx.author.name}`\n"
            f"**Reason:** `{reason}`"
        )
        container = ui.box(
            ui.text(f"# {E('AFK')} AFK Status Set"),
            ui.sep(),
            ui.section(body, ui.thumb(ctx.author.display_avatar.url)),
        )
        await ctx.send(view=ui.layout(container))

    def media_view(self, title, url, footer_text):
        dot = E('DOT')
        return ui.layout(
            ui.box(
                ui.text(f"# {E('UTILITY')} {title}\n{quote(dot + ' [Download](' + url + ')')}"),
                ui.gallery(url),
                ui.text(f"-# {config.BOT_NAME} • {footer_text}"),
            )
        )

    @commands.hybrid_command(name="avatar", aliases=["av"], description="Show a user's avatar.")
    async def avatar(self, ctx, user: Optional[discord.User] = None):
        user = user or ctx.author
        url = user.display_avatar.replace(size=1024).url
        await ctx.send(view=self.media_view(f"{user.display_name}'s Avatar", url, user.id))

    @commands.hybrid_command(name="banner", description="Show a user's banner.")
    async def banner(self, ctx, user: Optional[discord.User] = None):
        user = user or ctx.author
        fetched = await self.bot.fetch_user(user.id)
        if not fetched.banner:
            await ctx.send(view=ui.failure(f"**{user.display_name}** does not have a banner."))
            return
        await ctx.send(view=self.media_view(f"{user.display_name}'s Banner", fetched.banner.replace(size=1024).url, user.id))

    @commands.hybrid_command(name="servericon", aliases=["guildicon"], description="Show the server icon.")
    @commands.guild_only()
    async def servericon(self, ctx):
        if not ctx.guild.icon:
            await ctx.send(view=ui.failure("This server does not have an icon."))
            return
        await ctx.send(view=self.media_view(f"{ctx.guild.name}'s Icon", ctx.guild.icon.replace(size=1024).url, ctx.guild.id))

    @commands.hybrid_command(name="serverbanner", aliases=["guildbanner"], description="Show the server banner.")
    @commands.guild_only()
    async def serverbanner(self, ctx):
        if not ctx.guild.banner:
            await ctx.send(view=ui.failure("This server does not have a banner."))
            return
        await ctx.send(view=self.media_view(f"{ctx.guild.name}'s Banner", ctx.guild.banner.replace(size=1024).url, ctx.guild.id))

    @commands.hybrid_command(name="serverinfo", aliases=["si", "guildinfo"], description="Show information about the server.")
    @commands.guild_only()
    async def serverinfo(self, ctx):
        guild = ctx.guild
        humans = sum(1 for member in guild.members if not member.bot)
        bots = len(guild.members) - humans
        created = int(guild.created_at.timestamp())
        static = sum(1 for emoji in guild.emojis if not emoji.animated)
        animated = len(guild.emojis) - static
        announcements = len([c for c in guild.channels if isinstance(c, discord.TextChannel) and c.is_news()])
        texts = len(guild.text_channels) - announcements
        total = len(guild.channels)
        roles = [role for role in reversed(guild.roles) if role != guild.default_role]
        shown = roles[: config.ROLE_LIST_LIMIT]
        role_text = ", ".join(role.mention for role in shown)
        if len(roles) > len(shown):
            role_text += f", and `{len(roles) - len(shown)} more...`"
        features = ", ".join(feature.replace("_", " ").title() for feature in guild.features) or "None"
        owner = guild.owner.mention if guild.owner else f"<@{guild.owner_id}>"
        description = guild.description or "No server description set."
        title = f"# `{guild.name}'s Server Info`"
        icon = guild.icon.url if guild.icon else None
        head = ui.section(title, ui.thumb(icon)) if icon else ui.text(title)
        parts = [
            "### About Server\n"
            f"**Name:** `{guild.name}`\n**Owner:** {owner}\n"
            f"**Created:** <t:{created}:F> (<t:{created}:R>)\n"
            f"**ID:** `{guild.id}`\n**Total Members:** {number(guild.member_count)}",
            f"### Description\n• {description}",
            f"### Members\n• **Humans:** {number(humans)}\n• **Bots:** {number(bots)}\n• **Total:** {number(guild.member_count)}",
            "### Channels\n"
            f"• **Categories:** {len(guild.categories)}\n• **Text:** {texts}\n• **Announcements:** {announcements}\n"
            f"• **Forums:** {len(guild.forums)}\n• **Voice:** {len(guild.voice_channels)}\n"
            f"• **Stage:** {len(guild.stage_channels)}\n• **Total:** {total}",
            f"### Emojis & Stickers\n• **Static Emojis:** {static}\n• **Animated Emojis:** {animated}\n"
            f"• **Stickers:** {len(guild.stickers)}\n• **Combined Total:** {len(guild.emojis) + len(guild.stickers)}",
            f"### Server Settings\n• **Verification:** {guild.verification_level.name.title()}\n"
            f"• **Content Filter:** {guild.explicit_content_filter.name.replace('_', ' ').title()}\n"
            f"• **MFA Requirement:** {'Enabled' if guild.mfa_level.value else 'Disabled'}\n"
            f"• **Notifications:** {guild.default_notifications.name.replace('_', ' ').title()}",
            f"### Boosts\n• **Boost Level:** {guild.premium_tier or 'None'}\n"
            f"• **Boosts:** {guild.premium_subscription_count}\n• **Boosters:** {len(guild.premium_subscribers)}",
            f"### Features\n• {clip(features, 300)}",
            f"### Roles ({len(roles)})\n{clip(role_text, 900)}",
        ]
        items = [head, ui.sep()]
        for index, part in enumerate(parts):
            items.append(ui.text(part))
            if index in (0, 2, 3, 4, 6):
                items.append(ui.sep())
        items.append(ui.sep())
        items.append(ui.text(f"-# Requested by {ctx.author.name} • <t:{now()}:t>"))
        items.append(ui.row(ui.link("Server Icon", icon) if icon else ui.button(label="Server Icon", disabled=True)))
        await ctx.send(view=ui.layout(ui.box(*items)))

    @commands.hybrid_group(name="prefix", description="Show or change the server prefix.", invoke_without_command=True)
    @commands.guild_only()
    async def prefix(self, ctx):
        current = self.bot.prefix_for(ctx.guild)
        await ctx.send(view=ui.titled("UTILITY", "Prefix", f"The prefix for this server is `{current}`"))

    @prefix.command(name="set", description="Change the server prefix.")
    @commands.has_permissions(manage_guild=True)
    async def prefix_set(self, ctx, new_prefix: str):
        if len(new_prefix) > config.PREFIX_MAX_LENGTH or any(char.isspace() for char in new_prefix):
            await ctx.send(
                view=ui.failure(f"The prefix must be at most **{config.PREFIX_MAX_LENGTH}** characters without spaces.")
            )
            return
        self.bot.prefixes[ctx.guild.id] = new_prefix
        await self.bot.db.guild_set(ctx.guild.id, prefix=new_prefix)
        await ctx.send(view=ui.success(f"The prefix is now `{new_prefix}`"))

    @prefix.command(name="reset", description="Reset the server prefix.")
    @commands.has_permissions(manage_guild=True)
    async def prefix_reset(self, ctx):
        self.bot.prefixes.pop(ctx.guild.id, None)
        await self.bot.db.guild_set(ctx.guild.id, prefix=None)
        await ctx.send(view=ui.success(f"The prefix has been reset to `{config.DEFAULT_PREFIX}`"))

    @commands.hybrid_group(name="joinmsg", description="Manage the DM sent to new members.", invoke_without_command=True)
    @commands.guild_only()
    async def joinmsg(self, ctx):
        template = await self.bot.db.guild_value(ctx.guild.id, "joinmsg")
        prefix = ctx.clean_prefix
        variables = ", ".join(f"`{name}`" for name in config.WELCOME_VARIABLES[:4])
        body = (
            f"**Current message:** {clip(template, 500) if template else '`Not set`'}\n\n"
            f"{quote(f'`{prefix}joinmsg set <message>` — Set the DM message.', f'`{prefix}joinmsg remove` — Disable it.', f'`{prefix}joinmsg test` — Preview it.')}\n\n"
            f"**Variables:** {variables}"
        )
        await ctx.send(view=ui.titled("UTILITY", "Join Message", body))

    @joinmsg.command(name="set", description="Set the join DM message.")
    @commands.has_permissions(manage_guild=True)
    async def joinmsg_set(self, ctx, *, message: str):
        await self.bot.db.guild_set(ctx.guild.id, joinmsg=clip(message, 1500))
        await ctx.send(view=ui.success("The join message has been saved."))

    @joinmsg.command(name="remove", description="Disable the join DM message.")
    @commands.has_permissions(manage_guild=True)
    async def joinmsg_remove(self, ctx):
        await self.bot.db.guild_set(ctx.guild.id, joinmsg=None)
        await ctx.send(view=ui.success("The join message has been removed."))

    @joinmsg.command(name="test", description="Send yourself a preview.")
    @commands.has_permissions(manage_guild=True)
    async def joinmsg_test(self, ctx):
        template = await self.bot.db.guild_value(ctx.guild.id, "joinmsg")
        if not template:
            await ctx.send(view=ui.failure("No join message has been set."))
            return
        try:
            await ctx.author.send(apply_variables(template, ctx.author))
        except discord.HTTPException:
            await ctx.send(view=ui.failure("I could not send you a direct message."))
            return
        await ctx.send(view=ui.success("A preview has been sent to your DMs."))


async def setup(bot):
    await bot.add_cog(Utility(bot))
