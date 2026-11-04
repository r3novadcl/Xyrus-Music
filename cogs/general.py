import asyncio
from typing import Optional

import discord
from discord.ext import commands

import config
from utils import ui
from utils.emojis import E
from utils.help_view import HelpView
from utils.helpers import chips, fmt_expiry, invite_url, number, quote
from utils.images import render_team
from utils.stats_view import StatsView


class BuyView(ui.BaseView):
    def __init__(self, bot, author, guild, coins):
        super().__init__(author_id=author.id)
        self.bot = bot
        self.author = author
        self.guild = guild
        self.coins = coins
        self.add_item(self.build())

    def plan_select(self, label, plans, kind):
        options = [
            discord.SelectOption(
                label=f"{plan['label']} ({number(plan['price'])} coins)",
                value=str(index),
                emoji=E.partial("PLAN"),
            )
            for index, plan in enumerate(plans)
        ]

        async def callback(interaction):
            await self.purchase(interaction, kind, int(interaction.data["values"][0]))

        return ui.row(ui.select(label, options, callback))

    def build(self):
        body = (
            f"{E('COIN')} **You have a total of {number(self.coins)} coins**\n\n"
            f"{E('USAGE')} **Upgrade to Premium Unlock More Buy Now [Premium Page]({config.PREMIUM_PAGE_URL})**\n\n"
            f"{config.CURRENCY_NOTICE}"
        )
        return ui.box(
            ui.text(body),
            ui.sep(),
            self.plan_select("Choose your premium plan (User)", config.PLANS_USER, "user"),
            self.plan_select("Choose your premium plan (Guild)", config.PLANS_GUILD, "guild"),
        )

    async def purchase(self, interaction, kind, index):
        plans = config.PLANS_USER if kind == "user" else config.PLANS_GUILD
        plan = plans[index]
        balance = await self.bot.db.coins(self.author.id)
        if balance < plan["price"]:
            await interaction.response.send_message(
                view=ui.failure(
                    f"You need **{number(plan['price'])}** coins but you only have **{number(balance)}** coins."
                ),
                ephemeral=True,
            )
            return
        if kind == "guild":
            allowed = self.guild and self.author.guild_permissions.manage_guild
            if not allowed:
                await interaction.response.send_message(
                    view=ui.failure("You need the **Manage Server** permission to buy guild premium."),
                    ephemeral=True,
                )
                return
        await self.bot.db.spend_coins(self.author.id, plan["price"])
        if kind == "user":
            until = await self.bot.db.grant("users", self.author.id, plan["days"])
        else:
            until = await self.bot.db.grant("guilds", self.guild.id, plan["days"])
        self.coins = balance - plan["price"]
        await self.redraw(interaction, self.build())
        await interaction.followup.send(
            view=ui.success(f"**{plan['label']}** activated. Expires: {fmt_expiry(until)}"), ephemeral=True
        )


class General(commands.Cog):
    category = "general"

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show the help menu.")
    async def help(self, ctx, command: Optional[str] = None):
        prefix = ctx.clean_prefix
        if command:
            target = self.bot.get_command(command.lower())
            category = getattr(target.cog, "category", None) if target else None
            if not target or target.hidden or category in (None, "owner"):
                await ctx.send(view=ui.failure(f"No command named `{command}` was found."))
                return
            lines = [
                f"# {E('HELP')} {target.qualified_name}",
                target.description or target.help or "No description provided.",
                "",
                quote(
                    f"{E('DOT')} **Usage:** `{prefix}{target.qualified_name} {target.signature}`",
                    f"{E('DOT')} **Aliases:** {chips(target.aliases) if target.aliases else '`None`'}",
                    f"{E('DOT')} **Category:** `{config.CATEGORIES[category]['label']}`",
                ),
            ]
            await ctx.send(view=ui.plain("\n".join(lines)))
            return
        view = HelpView(self.bot, ctx.author.id, self.bot.prefix_for(ctx.guild))
        await ui.send(ctx, view)

    @commands.hybrid_command(name="info", description="Show information about the bot.")
    async def info(self, ctx):
        users = sum(guild.member_count or 0 for guild in self.bot.guilds)
        prefix = self.bot.prefix_for(ctx.guild)
        body = (
            f"# {E('MUSIC')} {config.BOT_NAME}\n\n"
            + quote(
                f"{E('SETTINGS')} **Bot Settings**",
                f"{E('DOT')} **Prefix:** `{prefix}`",
                f"{E('DOT')} **Command Mode:** `{config.COMMAND_MODE}`",
            )
            + "\n\n"
            + quote(
                f"{E('STATS')} **Bot Statistics**",
                f"{E('DOT')} **Servers:** {number(len(self.bot.guilds))}",
                f"{E('DOT')} **Users:** {number(users)}",
            )
            + f"\n\n-# Use `{prefix}help` or type `/` to explore commands!"
        )
        container = ui.box(
            ui.text(body),
            ui.row(
                ui.link("Support Server", config.SUPPORT_URL),
                ui.link(f"Invite {config.BOT_NAME}", invite_url(self.bot)),
            ),
        )
        await ctx.send(view=ui.layout(container))

    @commands.hybrid_command(name="invite", description="Get the bot invite link.")
    async def invite(self, ctx):
        container = ui.box(
            ui.text(
                f"# {E('DOT')} Invite {config.BOT_NAME}\n"
                f"Click the button below to invite **{config.BOT_NAME}** to your server!"
            ),
            ui.row(ui.link("Invite Me", invite_url(self.bot))),
        )
        await ctx.send(view=ui.layout(container))

    @commands.hybrid_command(name="ping", description="Check the bot latency.")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        await ctx.send(
            view=ui.plain(
                f"# {config.BOT_NAME} Latency\n{E('PONG')} Pong! \n\n**Websocket Latency:** {latency}ms"
            )
        )

    @commands.hybrid_command(name="support", description="Get the support server link.")
    async def support(self, ctx):
        container = ui.box(
            ui.text(f"# {E('INFO')} Support Server\nNeed help or have questions? Join our support server!"),
            ui.row(ui.link("Join Support Server", config.SUPPORT_URL)),
        )
        await ctx.send(view=ui.layout(container))

    @commands.hybrid_command(name="vote", description="Vote for the bot.")
    async def vote(self, ctx):
        if not config.VOTE_URL:
            await ctx.send(view=ui.failure("Voting is not available right now."))
            return
        container = ui.box(
            ui.text(f"# {E('SUCCESS')} Vote {config.BOT_NAME}\nSupport **{config.BOT_NAME}** by voting for it!"),
            ui.row(ui.link("Vote", config.VOTE_URL)),
        )
        await ctx.send(view=ui.layout(container))

    @commands.hybrid_command(name="stats", description="Show detailed bot statistics.")
    async def stats(self, ctx):
        await ui.send(ctx, StatsView(self.bot, ctx.author.id))

    @commands.hybrid_command(name="profile", description="Show your profile.")
    async def profile(self, ctx, user: Optional[discord.User] = None):
        user = user or ctx.author
        db = self.bot.db
        noprefix_until = await db.user_value(user.id, "noprefix_until", 0)
        noprefix_active = self.bot.has_noprefix(user.id) or noprefix_until == -1
        premium = await self.bot.is_premium(user.id) and user.id not in self.bot.owner_ids
        team = await db.scalar("SELECT 1 FROM team WHERE user_id = ?", user.id)
        earned = ["member"]
        if user.id in self.bot.owner_ids:
            earned.append("owner")
        if team:
            earned.append("team")
        if premium:
            earned.append("premium")
        if noprefix_active:
            earned.append("noprefix")
        badge_lines = [f"{E(config.BADGES[key]['emoji'])} {config.BADGES[key]['label']}" for key in earned]
        header = (
            f"# {E('INFO')} User Profile\n"
            f"### *{config.BOT_NAME} - Made By {config.TEAM_NAME}*\n\n"
            + quote(
                f"{E('DOT')} **User:** {user.mention}",
                f"{E('DOT')} **ID:** `{user.id}`",
                f"{E('DOT')} **Created:** <t:{int(user.created_at.timestamp())}:F>",
            )
            + "\n\n"
            + quote(
                f"{E('UTILITY')} **NoPrefix Status**",
                f"{E('DOT')} **Access:** `{'Granted' if noprefix_until else 'Not Granted'}`",
                f"{E('DOT')} **Status:** `{'Granted' if noprefix_active else 'Not Granted'}`",
            )
        )
        profile = ui.box(ui.section(header, ui.thumb(user.display_avatar.url)))
        badges = ui.box(ui.text(f"## {E('PREMIUM')} Badges Achieved\n{quote(*badge_lines)}"))
        await ctx.send(view=ui.layout(profile, badges))

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Check your coin balance.")
    async def balance(self, ctx):
        coins = await self.bot.db.coins(ctx.author.id)
        lines = [f"{E('COIN')} **You have a total of {number(coins)} coins**", "", "**Need coins ? Here's how you can get them:**", ""]
        for block in config.BALANCE_SECTIONS:
            lines.append(f"{E(block['emoji'])} **{block['title']}**")
            lines.extend(f"> {entry}" for entry in block["lines"])
            lines.append("")
        lines.append(config.CURRENCY_NOTICE)
        await ctx.send(view=ui.plain("\n".join(lines)))

    @commands.hybrid_command(name="buy", description="Buy premium with coins.")
    async def buy(self, ctx):
        coins = await self.bot.db.coins(ctx.author.id)
        await ui.send(ctx, BuyView(self.bot, ctx.author, ctx.guild, coins))

    @commands.hybrid_command(name="redeem", description="Redeem a premium code.")
    async def redeem(self, ctx, code: str):
        row = await self.bot.db.one("SELECT kind, days, uses FROM codes WHERE code = ?", code.strip())
        if row is None:
            await ctx.send(view=ui.failure("This code is invalid or has already been used."))
            return
        if row["kind"] == "guild":
            if not ctx.guild:
                await ctx.send(view=ui.failure("Guild codes must be redeemed inside a server."))
                return
            until = await self.bot.db.grant("guilds", ctx.guild.id, row["days"])
            target = f"**{ctx.guild.name}**"
        else:
            until = await self.bot.db.grant("users", ctx.author.id, row["days"])
            target = ctx.author.mention
        if row["uses"] <= 1:
            await self.bot.db.run("DELETE FROM codes WHERE code = ?", code.strip())
        else:
            await self.bot.db.run("UPDATE codes SET uses = uses - 1 WHERE code = ?", code.strip())
        await ctx.send(view=ui.success(f"Premium activated for {target}. Expires: {fmt_expiry(until)}"))

    @commands.hybrid_command(name="teams", description="Show the team behind the bot.")
    async def teams(self, ctx):
        await ctx.defer()
        rows = await self.bot.db.fetch("SELECT user_id, role FROM team ORDER BY added")
        if not rows:
            await ctx.send(view=ui.failure("No team members have been configured yet."))
            return
        order = {role: index for index, role in enumerate(config.TEAM_ROLES)}
        rows = sorted(rows, key=lambda row: order.get(row["role"], len(order)))
        members = []
        for row in rows:
            try:
                user = self.bot.get_user(row["user_id"]) or await self.bot.fetch_user(row["user_id"])
            except discord.HTTPException:
                continue
            avatar = await user.display_avatar.replace(size=128, format="png").read()
            members.append(
                {
                    "name": user.display_name,
                    "handle": user.name,
                    "id": user.id,
                    "role": row["role"],
                    "avatar": avatar,
                }
            )
        buffer = await asyncio.to_thread(render_team, config.BOT_NAME, members)
        await ctx.send(file=discord.File(buffer, filename="team.png"))


async def setup(bot):
    await bot.add_cog(General(bot))
