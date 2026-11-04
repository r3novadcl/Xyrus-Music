import logging
import random

import discord
from discord.ext import commands

import config
from utils import ui
from utils.helpers import number

log = logging.getLogger("events")


class Events(commands.Cog):
    category = None

    def __init__(self, bot):
        self.bot = bot

    async def log_event(self, title, guild):
        if not config.LOG_CHANNEL_ID:
            return
        channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if channel is None:
            return
        body = (
            f"**{guild.name}** (`{guild.id}`)\n"
            f"**Members:** {number(guild.member_count or 0)}\n"
            f"**Servers:** {number(len(self.bot.guilds))}"
        )
        try:
            await channel.send(view=ui.titled("INFO", title, body))
        except discord.HTTPException:
            log.warning("Could not send the guild log")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if guild.owner_id:
            await self.bot.db.add_coins(guild.owner_id, config.COIN_GUILD_JOIN)
        await self.log_event("Joined a Server", guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.log_event("Left a Server", guild)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.cog is not None and getattr(ctx.cog, "category", None) in (None, "owner"):
            return
        await self.bot.db.add_coins(ctx.author.id, random.randint(*config.COIN_PER_COMMAND))


async def setup(bot):
    await bot.add_cog(Events(bot))
