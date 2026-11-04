import discord

import config
from utils import ui
from utils.emojis import E
from utils.helpers import chips, invite_url, quote


class HelpView(ui.BaseView):
    def __init__(self, bot, author_id, prefix, page="home"):
        super().__init__(author_id=author_id)
        self.bot = bot
        self.prefix = prefix
        self.page = page
        self.add_item(self.build())

    def stats_block(self):
        return quote(
            f"{E('INFO')} **Statistics**",
            f"{E('DOT')} **Commands:** `{len(self.bot.visible_commands())}`",
            f"{E('DOT')} **Prefix:** `{self.prefix}`",
        )

    def body(self):
        if self.page == "home":
            categories = quote(
                *[
                    f"{E(config.CATEGORIES[key]['emoji'])} `:` **{config.CATEGORIES[key]['label']}**"
                    for key in config.HELP_LIST_ORDER
                ]
            )
            return (
                f"# {E('HELP')} {config.BOT_NAME} Help Menu\n\n"
                f"{self.stats_block()}\n"
                f"## {E('CATEGORIES')} **Command Categories**\n\n"
                f"{categories}\n\n"
                "-# Select a category from the dropdown below to explore commands!"
            )
        label = config.CATEGORIES[self.page]["label"]
        names = [command.name for command in self.bot.visible_commands(self.page)]
        return (
            f"# {E('HELP')} {config.BOT_NAME} Help Menu\n\n"
            f"{self.stats_block()}\n\n"
            f"## {label} Commands:\n{quote(chips(names))}"
        )

    def options(self):
        entries = [("home", config.HOME_OPTION)] + list(config.CATEGORIES.items())
        return [
            discord.SelectOption(
                label=data["label"],
                value=key,
                description=data["description"],
                emoji=E.partial(data["emoji"]),
                default=key == self.page and self.page != "home",
            )
            for key, data in entries
        ]

    def build(self):
        items = [ui.text(self.body())]
        if config.BANNER_URL:
            items.append(ui.gallery(config.BANNER_URL))
        items.append(ui.sep())
        items.append(ui.row(ui.select("Select a category...", self.options(), self.on_select)))
        items.append(
            ui.row(
                ui.link("Invite Bot", invite_url(self.bot)),
                ui.link("Support Server", config.SUPPORT_URL),
            )
        )
        return ui.box(*items)

    async def on_select(self, interaction):
        self.page = interaction.data["values"][0]
        await self.redraw(interaction, self.build())


class MentionView(ui.BaseView):
    def __init__(self, bot, author, prefix):
        super().__init__(author_id=None)
        self.bot = bot
        self.author = author
        self.prefix = prefix
        self.add_item(
            ui.box(
                ui.text(
                    f"{E('SUCCESS')} **Hey {author.mention}!**\n\n"
                    f"{E('INFO')} **My prefix for this server is `{prefix}`**\n\n"
                    f"{E('INFO')} **Type `{prefix}help` for a list of commands.**"
                ),
                ui.row(ui.button(label="Open Help Menu", emoji=E.partial("HELP"), callback=self.on_open)),
            )
        )

    async def on_open(self, interaction):
        view = HelpView(self.bot, interaction.user.id, self.prefix)
        await interaction.response.send_message(view=view)
        view.message = await interaction.original_response()
