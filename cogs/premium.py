import base64
from typing import Optional

import discord
from discord.ext import commands

import config
from utils import ui
from utils.checks import premium_only
from utils.helpers import clip

SIGNATURES = (
    (b"\x89PNG", "image/png"),
    (b"GIF8", "image/gif"),
    (b"\xff\xd8", "image/jpeg"),
)


def data_uri(data):
    mime = None
    for signature, value in SIGNATURES:
        if data.startswith(signature):
            mime = value
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    if mime is None:
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


class Premium(commands.Cog):
    category = "premium"

    def __init__(self, bot):
        self.bot = bot

    async def patch_profile(self, ctx, **payload):
        route = discord.http.Route("PATCH", "/guilds/{guild_id}/members/@me", guild_id=ctx.guild.id)
        try:
            await self.bot.http.request(route, json=payload)
        except discord.HTTPException as error:
            await ctx.send(view=ui.failure(f"Discord rejected the change: {clip(error.text, 150)}"))
            return False
        return True

    async def read_image(self, ctx, image, url):
        if image is not None:
            data = await image.read()
        elif url:
            async with self.bot.session.get(url) as response:
                if response.status != 200:
                    await ctx.send(view=ui.failure("I could not download that image."))
                    return None
                data = await response.read()
        else:
            await ctx.send(view=ui.usage_error(f"{ctx.clean_prefix}{ctx.command.name} <attachment|url>"))
            return None
        encoded = data_uri(data)
        if encoded is None:
            await ctx.send(view=ui.failure("The image must be a PNG, JPG, GIF or WEBP file."))
        return encoded

    @commands.hybrid_command(name="botname", description="Change the bot nickname in this server.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @premium_only()
    async def botname(self, ctx, *, name: str):
        if await self.patch_profile(ctx, nick=clip(name, 32)):
            await ctx.send(view=ui.success(f"The bot nickname is now **{clip(name, 32)}**."))

    @commands.hybrid_command(name="botavatar", description="Change the bot avatar in this server.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @premium_only()
    async def botavatar(self, ctx, image: Optional[discord.Attachment] = None, url: Optional[str] = None):
        encoded = await self.read_image(ctx, image, url)
        if encoded and await self.patch_profile(ctx, avatar=encoded):
            await ctx.send(view=ui.success("The bot avatar has been updated for this server."))

    @commands.hybrid_command(name="botbanner", description="Change the bot banner in this server.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @premium_only()
    async def botbanner(self, ctx, image: Optional[discord.Attachment] = None, url: Optional[str] = None):
        encoded = await self.read_image(ctx, image, url)
        if encoded and await self.patch_profile(ctx, banner=encoded):
            await ctx.send(view=ui.success("The bot banner has been updated for this server."))

    @commands.hybrid_command(name="botbio", description="Change the bot bio in this server.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @premium_only()
    async def botbio(self, ctx, *, bio: str):
        if await self.patch_profile(ctx, bio=clip(bio, 190)):
            await ctx.send(view=ui.success("The bot bio has been updated for this server."))

    @commands.hybrid_command(name="botreset", description="Reset the bot profile in this server.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @premium_only()
    async def botreset(self, ctx):
        if await self.patch_profile(ctx, nick=None, avatar=None, banner=None, bio=None):
            await ctx.send(view=ui.success(f"The {config.BOT_NAME} profile has been reset for this server."))


async def setup(bot):
    await bot.add_cog(Premium(bot))
