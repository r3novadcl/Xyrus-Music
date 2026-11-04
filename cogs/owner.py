import secrets
from typing import Literal

import discord
from discord.ext import commands

import config
from utils import ui
from utils.emojis import E
from utils.helpers import extend_until, fmt_expiry, now, number, quote


class Owner(commands.Cog):
    category = "owner"

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="ownerhelp", aliases=["ownermenu"], hidden=True)
    async def ownerhelp(self, ctx):
        prefix = ctx.clean_prefix
        items = [ui.text(f"# {E('SETTINGS')} {config.BOT_NAME} Owner Menu"), ui.sep()]
        for group in config.OWNER_HELP:
            lines = [f"{E('DOT')} `{prefix}{usage}` — {description}" for usage, description in group["commands"]]
            items.append(ui.text(f"## {E(group['emoji'])} {group['title']}\n{quote(*lines)}"))
        items.append(ui.footer("Owner only"))
        await ctx.send(view=ui.layout(ui.box(*items)))

    @commands.group(name="noprefix", hidden=True, invoke_without_command=True)
    async def noprefix(self, ctx):
        await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}noprefix add|remove|list"))

    @noprefix.command(name="add")
    async def noprefix_add(self, ctx, user: discord.User, days: int = -1):
        current = await self.bot.db.user_value(user.id, "noprefix_until", 0)
        until = extend_until(current, days)
        await self.bot.db.user_set(user.id, noprefix_until=until)
        self.bot.noprefix[user.id] = until
        await ctx.send(view=ui.success(f"NoPrefix granted to {user.mention}. Expires: {fmt_expiry(until)}"))

    @noprefix.command(name="remove")
    async def noprefix_remove(self, ctx, user: discord.User):
        await self.bot.db.user_set(user.id, noprefix_until=0)
        self.bot.noprefix.pop(user.id, None)
        await ctx.send(view=ui.success(f"NoPrefix removed from {user.mention}."))

    @noprefix.command(name="list")
    async def noprefix_list(self, ctx):
        rows = await self.bot.db.fetch("SELECT user_id, noprefix_until FROM users WHERE noprefix_until != 0")
        body = "\n".join(f"<@{row['user_id']}> • {fmt_expiry(row['noprefix_until'])}" for row in rows) or "`None`"
        await ctx.send(view=ui.titled("UTILITY", "NoPrefix Users", body))

    @commands.group(name="premium", hidden=True, invoke_without_command=True)
    async def premium(self, ctx):
        await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}premium user|guild|revoke|list"))

    @premium.command(name="user")
    async def premium_user(self, ctx, user: discord.User, days: int = -1):
        until = await self.bot.db.grant("users", user.id, days)
        await ctx.send(view=ui.success(f"Premium granted to {user.mention}. Expires: {fmt_expiry(until)}"))

    @premium.command(name="guild")
    async def premium_guild(self, ctx, guild_id: int, days: int = -1):
        until = await self.bot.db.grant("guilds", guild_id, days)
        await ctx.send(view=ui.success(f"Premium granted to guild `{guild_id}`. Expires: {fmt_expiry(until)}"))

    @premium.command(name="revoke")
    async def premium_revoke(self, ctx, kind: Literal["user", "guild"], target_id: int):
        await self.bot.db.revoke("users" if kind == "user" else "guilds", target_id)
        await ctx.send(view=ui.success(f"Premium revoked for `{target_id}`."))

    @premium.command(name="list")
    async def premium_list(self, ctx):
        users = await self.bot.db.fetch("SELECT user_id, premium_until FROM users WHERE premium_until != 0")
        guilds = await self.bot.db.fetch("SELECT guild_id, premium_until FROM guilds WHERE premium_until != 0")
        lines = [f"<@{row['user_id']}> • {fmt_expiry(row['premium_until'])}" for row in users]
        lines += [f"Guild `{row['guild_id']}` • {fmt_expiry(row['premium_until'])}" for row in guilds]
        await ctx.send(view=ui.titled("PREMIUM", "Premium Holders", "\n".join(lines) or "`None`"))

    @commands.command(name="gencode", hidden=True)
    async def gencode(self, ctx, kind: Literal["user", "guild"], days: int, uses: int = 1):
        raw = secrets.token_hex(6).upper()
        code = "-".join(raw[index : index + 4] for index in range(0, 12, 4))
        await self.bot.db.run(
            "INSERT INTO codes (code, kind, days, uses) VALUES (?, ?, ?, ?)", code, kind, days, max(uses, 1)
        )
        duration = "Lifetime" if days == -1 else f"{days} days"
        await ctx.send(view=ui.success(f"Code: `{code}`\nType: **{kind}** • Duration: **{duration}** • Uses: **{max(uses, 1)}**"))

    @commands.group(name="coins", hidden=True, invoke_without_command=True)
    async def coins(self, ctx):
        await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}coins add|remove <user> <amount>"))

    @coins.command(name="add")
    async def coins_add(self, ctx, user: discord.User, amount: int):
        await self.bot.db.add_coins(user.id, abs(amount))
        total = await self.bot.db.coins(user.id)
        await ctx.send(view=ui.success(f"{user.mention} now has **{number(total)}** coins."))

    @coins.command(name="remove")
    async def coins_remove(self, ctx, user: discord.User, amount: int):
        await self.bot.db.add_coins(user.id, -abs(amount))
        total = await self.bot.db.coins(user.id)
        await ctx.send(view=ui.success(f"{user.mention} now has **{number(total)}** coins."))

    @commands.group(name="team", hidden=True, invoke_without_command=True)
    async def team(self, ctx):
        await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}team add|remove|list"))

    @team.command(name="add")
    async def team_add(self, ctx, user: discord.User, role: str):
        role = role.lower()
        if role not in config.TEAM_ROLES:
            await ctx.send(view=ui.failure(f"The role must be one of: {', '.join(f'`{r}`' for r in config.TEAM_ROLES)}"))
            return
        await self.bot.db.run(
            "INSERT INTO team (user_id, role, added) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET role = excluded.role",
            user.id,
            role,
            now(),
        )
        await ctx.send(view=ui.success(f"{user.mention} is now on the team as **{role}**."))

    @team.command(name="remove")
    async def team_remove(self, ctx, user: discord.User):
        await self.bot.db.run("DELETE FROM team WHERE user_id = ?", user.id)
        await ctx.send(view=ui.success(f"{user.mention} has been removed from the team."))

    @team.command(name="list")
    async def team_list(self, ctx):
        rows = await self.bot.db.fetch("SELECT user_id, role FROM team ORDER BY added")
        body = "\n".join(f"<@{row['user_id']}> • `{row['role']}`" for row in rows) or "`None`"
        await ctx.send(view=ui.titled("TEAM", "Team Members", body))

    @commands.command(name="sync", hidden=True)
    async def sync(self, ctx):
        synced = await self.bot.tree.sync()
        await ctx.send(view=ui.success(f"Synced **{len(synced)}** slash commands."))

    @commands.command(name="reload", hidden=True)
    async def reload(self, ctx, extension: str):
        await self.bot.reload_extension(f"cogs.{extension}")
        await ctx.send(view=ui.success(f"Reloaded `{extension}`."))


async def setup(bot):
    await bot.add_cog(Owner(bot))
