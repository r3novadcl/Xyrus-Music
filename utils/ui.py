import discord

import config
from utils.emojis import E


def accent():
    return discord.Colour(config.ACCENT_COLOR)


def text(content):
    return discord.ui.TextDisplay(content)


def sep(visible=True, large=False):
    spacing = discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small
    return discord.ui.Separator(visible=visible, spacing=spacing)


def section(content, accessory):
    return discord.ui.Section(discord.ui.TextDisplay(content), accessory=accessory)


def thumb(url):
    return discord.ui.Thumbnail(url)


def gallery(*urls):
    return discord.ui.MediaGallery(*[discord.MediaGalleryItem(url) for url in urls])


def row(*items):
    return discord.ui.ActionRow(*items)


def link(label, url, emoji=None):
    return discord.ui.Button(label=label, url=url, style=discord.ButtonStyle.link, emoji=emoji)


def button(label=None, emoji=None, style=discord.ButtonStyle.secondary, callback=None, disabled=False):
    item = discord.ui.Button(label=label, emoji=emoji, style=style, disabled=disabled)
    if callback:
        item.callback = callback
    return item


def select(placeholder, options, callback):
    item = discord.ui.Select(placeholder=placeholder, options=options, min_values=1, max_values=1)
    item.callback = callback
    return item


def box(*children, colour=None):
    return discord.ui.Container(*children, accent_colour=colour or accent())


def layout(*containers, timeout=None):
    view = discord.ui.LayoutView(timeout=timeout)
    for container in containers:
        view.add_item(container)
    return view


def titled(emoji_key, title, body):
    return layout(box(text(f"# {E(emoji_key)} {title}"), sep(), text(body)))


def success(body, title="Success"):
    return titled("SUCCESS", title, body)


def failure(body, title="Error"):
    return titled("ERROR", title, body)


def plain(body):
    return layout(box(text(body)))


def usage_error(usage):
    return plain(f"{E('ERROR')} **Invalid/No args provided**\n\n{E('USAGE')} Usage: `{usage}`")


def footer(extra=None):
    base = f"{config.BOT_NAME} • {extra}" if extra else f"{config.BOT_NAME} • Made By {config.TEAM_NAME}"
    return text(f"-# {base}")


def iter_items(view):
    walker = getattr(view, "walk_children", None)
    if walker:
        return list(walker())
    return list(view.children)


class BaseView(discord.ui.LayoutView):
    def __init__(self, author_id=None, timeout=config.VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.message = None

    async def interaction_check(self, interaction):
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(
                view=failure(f"Only <@{self.author_id}> can use this."), ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in iter_items(self):
            if isinstance(item, (discord.ui.Button, discord.ui.Select)) and not getattr(item, "url", None):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def redraw(self, interaction, container):
        self.clear_items()
        self.add_item(container)
        await interaction.response.edit_message(view=self)


async def send(ctx, view, **kwargs):
    message = await ctx.send(view=view, **kwargs)
    if isinstance(view, BaseView):
        view.message = message
    return message
