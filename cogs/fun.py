import hashlib
from typing import Optional

import discord
from discord.ext import commands

import config
from utils import ui
from utils.emojis import E
from utils.helpers import quote


class Fun(commands.Cog):
    category = "fun"

    def __init__(self, bot):
        self.bot = bot

    async def fetch_gif(self, action):
        try:
            async with self.bot.session.get(config.FUN_API.format(action=action)) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                return data["results"][0]["url"]
        except Exception:
            return None

    async def interact(self, ctx, action, member):
        url = await self.fetch_gif(action)
        if url is None:
            await ctx.send(view=ui.failure("I could not fetch a gif right now. Try again later."))
            return
        line = config.FUN_ACTIONS[action].format(author=ctx.author.display_name, target=member.display_name)
        container = ui.box(
            ui.text(f"{E('FUN')} {line}"),
            ui.gallery(url),
            ui.text(f"-# {config.FUN_CREDIT}"),
        )
        await ctx.send(view=ui.layout(container))

    @commands.hybrid_command(name="hug", description="Hug someone.")
    @commands.guild_only()
    async def hug(self, ctx, member: discord.Member):
        await self.interact(ctx, "hug", member)

    @commands.hybrid_command(name="pat", description="Pat someone.")
    @commands.guild_only()
    async def pat(self, ctx, member: discord.Member):
        await self.interact(ctx, "pat", member)

    @commands.hybrid_command(name="slap", description="Slap someone.")
    @commands.guild_only()
    async def slap(self, ctx, member: discord.Member):
        await self.interact(ctx, "slap", member)

    @commands.hybrid_command(name="ship", description="Check how well two people match.")
    @commands.guild_only()
    async def ship(self, ctx, first: discord.Member, second: Optional[discord.Member] = None):
        second = second or ctx.author
        key = "-".join(str(value) for value in sorted((first.id, second.id)))
        percent = int(hashlib.md5(key.encode()).hexdigest(), 16) % 101
        filled = percent * config.SHIP_BAR_LENGTH // 100
        bar = "█" * filled + "░" * (config.SHIP_BAR_LENGTH - filled)
        verdict = next(text for limit, text in config.SHIP_TIERS if percent < limit)
        body = (
            f"# {E('FUN')} Ship\n**{first.display_name}** × **{second.display_name}**\n"
            + quote(f"`{bar}` **{percent}%**", verdict)
        )
        await ctx.send(view=ui.plain(body))


async def setup(bot):
    await bot.add_cog(Fun(bot))
