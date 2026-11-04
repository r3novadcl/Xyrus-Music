import json
from pathlib import Path

import discord

import config


class EmojiMap:
    def __init__(self):
        self.entries = {}
        self.uploaded = {}
        self.reload()

    @staticmethod
    def read(path):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def reload(self):
        self.entries = self.read(config.EMOJIS_FILE)
        self.uploaded = self.read(config.EMOJIS_UPLOADED_FILE)

    def record(self, key):
        item = self.uploaded.get(key)
        if item and item.get("id"):
            return item
        return None

    def __call__(self, key):
        item = self.record(key)
        if item:
            marker = "a" if item.get("animated") else ""
            return f"<{marker}:{item['name']}:{item['id']}>"
        return config.EMOJI_FALLBACKS.get(key, "")

    def __getitem__(self, key):
        return self(key)

    def partial(self, key):
        item = self.record(key)
        if item:
            return discord.PartialEmoji(
                name=item["name"], id=int(item["id"]), animated=bool(item.get("animated"))
            )
        return config.EMOJI_FALLBACKS.get(key) or None


E = EmojiMap()
