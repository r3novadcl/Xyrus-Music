from discord.ext import commands


class NotPremium(commands.CheckFailure):
    pass


def premium_only():
    async def predicate(ctx):
        if await ctx.bot.is_premium(ctx.author.id, ctx.guild.id if ctx.guild else None):
            return True
        raise NotPremium()

    return commands.check(predicate)
