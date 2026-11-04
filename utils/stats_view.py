import platform
import time

import discord
import psutil

import config
from utils import ui
from utils.emojis import E
from utils.helpers import fmt_uptime, number

try:
    import wavelink
except ImportError:
    wavelink = None


def line(label, value):
    return f"{E('DOT')} **{label}:** {value}"


def code(value):
    return f"`{value}`"


class StatsView(ui.BaseView):
    def __init__(self, bot, author_id):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.page = None
        self.add_item(self.home())

    def selector(self):
        options = [
            discord.SelectOption(
                label=data["label"],
                value=key,
                description=data["description"],
                emoji=E.partial(data["emoji"]),
            )
            for key, data in config.STATS_PAGES.items()
        ]
        return ui.row(ui.select("Select statistic category...", options, self.on_select))

    def home(self):
        return ui.box(
            ui.text(
                f"# {E('STATS')} {config.BOT_NAME} Stats\n"
                f"{E('DOT')} Please select a category from the dropdown below to view statistics.\n"
                f"-# {config.BOT_NAME} • {config.VERSION}"
            ),
            self.selector(),
        )

    async def build(self, page):
        bot = self.bot
        if page == "general":
            users = sum(guild.member_count or 0 for guild in bot.guilds)
            body = "\n".join(
                [
                    f"# {E('INFO')} General Statistics",
                    line("Total Guilds", code(number(len(bot.guilds)))),
                    line("Total Users", code(number(users))),
                    line("Shards", code(bot.shard_count or 1)),
                    line("Uptime", code(fmt_uptime(time.time() - bot.started_at))),
                    line("Gateway Ping", code(f"{round(bot.latency * 1000)}ms")),
                ]
            )
        elif page == "owner":
            body = "\n".join(
                [
                    f"# {E('TEAM')} Development Team",
                    line("Lead Developer", code(config.LEAD_DEVELOPERS)),
                    line("Contributors", code(config.CONTRIBUTORS)),
                    line("Support Server", f"[Click Here]({config.SUPPORT_URL})"),
                ]
            )
        elif page == "system":
            process = psutil.Process()
            used = process.memory_info().rss / 1024 / 1024
            total = psutil.virtual_memory().total / 1024 / 1024
            size = config.DB_PATH.stat().st_size / 1024 / 1024 if config.DB_PATH.exists() else 0
            body = "\n".join(
                [
                    f"# {E('INFO')} System Statistics",
                    line("Python Version", code(f"v{platform.python_version()}")),
                    line("Operating System", code(f"{platform.system()} {platform.release()}")),
                    line("Memory Usage", code(f"{used:.2f} MB / {total:.2f} MB")),
                    line("CPU Usage", code(f"{psutil.cpu_percent(interval=None):.1f}%")),
                    line("CPU Arch", code(platform.machine())),
                    line("Database Size", code(f"{size:.2f} MB")),
                ]
            )
        elif page == "ping":
            started = time.perf_counter()
            await bot.db.scalar("SELECT 1")
            database = (time.perf_counter() - started) * 1000
            body = "\n".join(
                [
                    f"# {E('LATENCY')} Latency Statistics",
                    line("Gateway Ping", code(f"{round(bot.latency * 1000)}ms")),
                    line("Database Ping", code(f"{database:.1f}ms")),
                ]
            )
        else:
            rows = [f"# {E('MUSIC')} Music Node Statistics"]
            nodes = list(wavelink.Pool.nodes.values()) if wavelink else []
            if not nodes:
                rows.append(line("Node State", code("Not configured")))
            for node in nodes:
                state = "Connected" if node.status is wavelink.NodeStatus.CONNECTED else "Disconnected"
                rows.append(line("Node Name", code(node.identifier)))
                rows.append(line("Node State", code(state)))
                rows.append(line("Active Players", code(len(node.players))))
            body = "\n".join(rows)
        return ui.box(ui.text(body), ui.footer(), self.selector())

    async def on_select(self, interaction):
        self.page = interaction.data["values"][0]
        container = await self.build(self.page)
        await self.redraw(interaction, container)
