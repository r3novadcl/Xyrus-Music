import logging
import time

import aiohttp
import discord
from discord.ext import commands

import config
from utils import emoji_sync, ui
from utils.checks import NotPremium
from utils.db import Database
from utils.emojis import E
from utils.help_view import MentionView
from utils.helpers import active

log = logging.getLogger("bot")


class XyrusBot(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(
            command_prefix=self.resolve_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
            owner_ids=set(config.OWNER_IDS),
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False),
        )
        self.started_at = time.time()
        self.session = None
        self.backdrop = None
        self.db = None
        self.prefixes = {}
        self.noprefix = {}
        self.ignored = {}
        self.afk = {}
        self.reacts = {}
        self.responds = {}
        self.add_check(self.global_check)

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.db = Database(config.DB_PATH)
        await self.db.connect()
        await self.load_caches()
        if config.EMOJI_AUTO_SYNC:
            try:
                await emoji_sync.sync(config.TOKEN, self.session)
                E.reload()
            except Exception:
                log.exception("Emoji sync failed")
        for extension in config.COGS:
            await self.load_extension(extension)
        if config.SYNC_ON_START:
            await self.tree.sync()

    async def close(self):
        if self.session:
            await self.session.close()
        if self.db:
            await self.db.close()
        await super().close()

    async def load_caches(self):
        for row in await self.db.fetch("SELECT guild_id, prefix FROM guilds WHERE prefix IS NOT NULL"):
            self.prefixes[row["guild_id"]] = row["prefix"]
        for row in await self.db.fetch("SELECT user_id, noprefix_until FROM users WHERE noprefix_until != 0"):
            self.noprefix[row["user_id"]] = row["noprefix_until"]
        for row in await self.db.fetch("SELECT guild_id, target_id FROM ignores"):
            self.ignored.setdefault(row["guild_id"], set()).add(row["target_id"])
        for row in await self.db.fetch("SELECT guild_id, user_id, reason, since FROM afk"):
            self.afk[(row["guild_id"], row["user_id"])] = {"reason": row["reason"], "since": row["since"], "mid": 0}
        for row in await self.db.fetch("SELECT guild_id, trigger, reaction FROM reacts"):
            self.reacts.setdefault(row["guild_id"], {})[row["trigger"]] = row["reaction"]
        for row in await self.db.fetch("SELECT guild_id, trigger, response FROM responds"):
            self.responds.setdefault(row["guild_id"], {})[row["trigger"]] = row["response"]

    def prefix_for(self, guild):
        if guild is None:
            return config.DEFAULT_PREFIX
        return self.prefixes.get(guild.id, config.DEFAULT_PREFIX)

    def has_noprefix(self, user_id):
        return active(self.noprefix.get(user_id, 0))

    async def resolve_prefix(self, bot, message):
        result = list(commands.when_mentioned(bot, message))
        result.append(self.prefix_for(message.guild))
        if self.has_noprefix(message.author.id):
            result.append("")
        return result

    def is_ignored(self, guild, channel_id, user_id):
        if guild is None:
            return False
        targets = self.ignored.get(guild.id)
        return bool(targets and (channel_id in targets or user_id in targets))

    def message_ignored(self, message):
        if not self.is_ignored(message.guild, message.channel.id, message.author.id):
            return False
        member = message.author
        if member.id in self.owner_ids:
            return False
        return not (isinstance(member, discord.Member) and member.guild_permissions.manage_guild)

    async def global_check(self, ctx):
        if ctx.author.id in self.owner_ids:
            return True
        if not self.is_ignored(ctx.guild, ctx.channel.id, ctx.author.id):
            return True
        return bool(ctx.guild and ctx.author.guild_permissions.manage_guild)

    async def is_premium(self, user_id, guild_id=None):
        if user_id in self.owner_ids:
            return True
        if active(await self.db.user_premium(user_id)):
            return True
        if guild_id and active(await self.db.guild_premium(guild_id)):
            return True
        return False

    def visible_commands(self, category=None):
        result = []
        for cog in self.cogs.values():
            cog_category = getattr(cog, "category", None)
            if cog_category is None or cog_category == "owner":
                continue
            if category and cog_category != category:
                continue
            result.extend(command for command in cog.get_commands() if not command.hidden)
        return sorted(result, key=lambda command: command.name)

    async def on_ready(self):
        text = config.PRESENCE_TEXT.format(prefix=config.DEFAULT_PREFIX, servers=len(self.guilds))
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=text))
        log.info("Logged in as %s (%s) in %s guilds", self.user, self.user.id, len(self.guilds))

    async def on_message(self, message):
        if message.author.bot:
            return
        if self.message_ignored(message):
            return
        if config.MENTION_REPLY and message.guild:
            content = message.content.strip()
            if content in (f"<@{self.user.id}>", f"<@!{self.user.id}>"):
                prefix = self.prefix_for(message.guild)
                view = MentionView(self, message.author, prefix)
                await message.reply(view=view)
                return
        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        error = getattr(error, "original", error)
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return
        if isinstance(error, NotPremium):
            await ctx.send(view=ui.titled("ERROR", f"{config.BOT_NAME} Premium", "This command is exclusively for Premium Users."))
            return
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
            usage = f"{ctx.clean_prefix}{ctx.command.qualified_name} {ctx.command.signature}".strip()
            await ctx.send(view=ui.usage_error(usage))
            return
        if isinstance(error, commands.MissingPermissions):
            missing = ", ".join(name.replace("_", " ").title() for name in error.missing_permissions)
            await ctx.send(view=ui.failure(f"You need the following permissions: **{missing}**"))
            return
        if isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(name.replace("_", " ").title() for name in error.missing_permissions)
            await ctx.send(view=ui.failure(f"I need the following permissions: **{missing}**"))
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(view=ui.failure(f"Try again in **{error.retry_after:.1f}s**."))
            return
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send(view=ui.failure("This command can only be used in a server."))
            return
        if isinstance(error, commands.CheckFailure):
            return
        log.error("Command %s failed", getattr(ctx.command, "qualified_name", "?"), exc_info=error)
        await ctx.send(view=ui.failure("Something went wrong while running this command."))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.TOKEN:
        raise SystemExit("TOKEN is missing. Copy .env.example to .env and fill it in.")
    XyrusBot().run(config.TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
