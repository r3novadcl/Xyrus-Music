import aiosqlite

import config
from utils.helpers import extend_until

SCHEMA = [
    (
        "CREATE TABLE IF NOT EXISTS guilds (\n"
        "    guild_id INTEGER PRIMARY KEY,\n"
        "    prefix TEXT,\n"
        "    engine TEXT,\n"
        "    volume INTEGER,\n"
        "    autoplay INTEGER NOT NULL DEFAULT 0,\n"
        "    joinmsg TEXT,\n"
        "    vc247 INTEGER NOT NULL DEFAULT 0,\n"
        "    voice_id INTEGER,\n"
        "    text_id INTEGER,\n"
        "    premium_until INTEGER NOT NULL DEFAULT 0\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS users (\n"
        "    user_id INTEGER PRIMARY KEY,\n"
        "    coins INTEGER NOT NULL DEFAULT 0,\n"
        "    premium_until INTEGER NOT NULL DEFAULT 0,\n"
        "    noprefix_until INTEGER NOT NULL DEFAULT 0\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS codes (\n"
        "    code TEXT PRIMARY KEY,\n"
        "    kind TEXT NOT NULL,\n"
        "    days INTEGER NOT NULL,\n"
        "    uses INTEGER NOT NULL DEFAULT 1\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS afk (\n"
        "    guild_id INTEGER NOT NULL,\n"
        "    user_id INTEGER NOT NULL,\n"
        "    reason TEXT NOT NULL,\n"
        "    since INTEGER NOT NULL,\n"
        "    PRIMARY KEY (guild_id, user_id)\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS afk_pings (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    guild_id INTEGER NOT NULL,\n"
        "    user_id INTEGER NOT NULL,\n"
        "    author_id INTEGER NOT NULL,\n"
        "    channel_id INTEGER NOT NULL,\n"
        "    message_id INTEGER NOT NULL,\n"
        "    content TEXT NOT NULL,\n"
        "    created INTEGER NOT NULL\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS ignores (\n"
        "    guild_id INTEGER NOT NULL,\n"
        "    target_id INTEGER NOT NULL,\n"
        "    kind TEXT NOT NULL,\n"
        "    PRIMARY KEY (guild_id, target_id)\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS reacts (\n"
        "    guild_id INTEGER NOT NULL,\n"
        "    trigger TEXT NOT NULL,\n"
        "    reaction TEXT NOT NULL,\n"
        "    PRIMARY KEY (guild_id, trigger)\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS responds (\n"
        "    guild_id INTEGER NOT NULL,\n"
        "    trigger TEXT NOT NULL,\n"
        "    response TEXT NOT NULL,\n"
        "    PRIMARY KEY (guild_id, trigger)\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS welcome (\n"
        "    guild_id INTEGER PRIMARY KEY,\n"
        "    enabled INTEGER NOT NULL DEFAULT 0,\n"
        "    channel_id INTEGER,\n"
        "    message TEXT,\n"
        "    title TEXT,\n"
        "    description TEXT,\n"
        "    color TEXT,\n"
        "    author_name TEXT,\n"
        "    author_icon TEXT,\n"
        "    footer_text TEXT,\n"
        "    footer_icon TEXT,\n"
        "    thumbnail TEXT,\n"
        "    image TEXT,\n"
        "    autodelete INTEGER NOT NULL DEFAULT 0\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS team (\n"
        "    user_id INTEGER PRIMARY KEY,\n"
        "    role TEXT NOT NULL,\n"
        "    added INTEGER NOT NULL\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS liked (\n"
        "    user_id INTEGER NOT NULL,\n"
        "    uri TEXT NOT NULL,\n"
        "    title TEXT NOT NULL,\n"
        "    author TEXT NOT NULL,\n"
        "    length INTEGER NOT NULL,\n"
        "    added INTEGER NOT NULL,\n"
        "    PRIMARY KEY (user_id, uri)\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS playlists (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    user_id INTEGER NOT NULL,\n"
        "    name TEXT NOT NULL,\n"
        "    UNIQUE (user_id, name)\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS playlist_tracks (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    playlist_id INTEGER NOT NULL,\n"
        "    uri TEXT NOT NULL,\n"
        "    title TEXT NOT NULL,\n"
        "    author TEXT NOT NULL,\n"
        "    length INTEGER NOT NULL\n"
        ")\n"
    ),
    (
        "CREATE TABLE IF NOT EXISTS song_plays (\n"
        "    guild_id INTEGER NOT NULL,\n"
        "    user_id INTEGER NOT NULL,\n"
        "    uri TEXT NOT NULL,\n"
        "    title TEXT NOT NULL,\n"
        "    author TEXT NOT NULL,\n"
        "    plays INTEGER NOT NULL DEFAULT 0,\n"
        "    PRIMARY KEY (guild_id, user_id, uri)\n"
        ")\n"
    ),
]


OWNERS = {"users": "user_id", "guilds": "guild_id"}


class Database:
    def __init__(self, path):
        self.path = path
        self.conn = None

    async def connect(self):
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        for statement in SCHEMA:
            await self.conn.execute(statement)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def fetch(self, sql, *args):
        cursor = await self.conn.execute(sql, args)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def one(self, sql, *args):
        cursor = await self.conn.execute(sql, args)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def scalar(self, sql, *args, default=None):
        row = await self.one(sql, *args)
        if row is None or row[0] is None:
            return default
        return row[0]

    async def run(self, sql, *args):
        cursor = await self.conn.execute(sql, args)
        await self.conn.commit()
        rowid = cursor.lastrowid
        await cursor.close()
        return rowid

    async def guild_value(self, guild_id, column, default=None):
        return await self.scalar(f"SELECT {column} FROM guilds WHERE guild_id = ?", guild_id, default=default)

    async def guild_set(self, guild_id, **columns):
        names = ", ".join(columns)
        marks = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{name} = excluded.{name}" for name in columns)
        await self.run(
            f"INSERT INTO guilds (guild_id, {names}) VALUES (?, {marks}) "
            f"ON CONFLICT(guild_id) DO UPDATE SET {updates}",
            guild_id,
            *columns.values(),
        )

    async def user_value(self, user_id, column, default=0):
        return await self.scalar(f"SELECT {column} FROM users WHERE user_id = ?", user_id, default=default)

    async def user_set(self, user_id, **columns):
        names = ", ".join(columns)
        marks = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{name} = excluded.{name}" for name in columns)
        await self.run(
            f"INSERT INTO users (user_id, {names}) VALUES (?, {marks}) "
            f"ON CONFLICT(user_id) DO UPDATE SET {updates}",
            user_id,
            *columns.values(),
        )

    async def coins(self, user_id):
        return await self.user_value(user_id, "coins", config.COIN_START)

    async def add_coins(self, user_id, amount):
        current = await self.coins(user_id)
        await self.user_set(user_id, coins=max(current + amount, 0))

    async def spend_coins(self, user_id, amount):
        current = await self.coins(user_id)
        if current < amount:
            return False
        await self.user_set(user_id, coins=current - amount)
        return True

    async def grant(self, table, target_id, days):
        column = OWNERS[table]
        current = await self.scalar(
            f"SELECT premium_until FROM {table} WHERE {column} = ?", target_id, default=0
        )
        until = extend_until(current, days)
        await self.run(
            f"INSERT INTO {table} ({column}, premium_until) VALUES (?, ?) "
            f"ON CONFLICT({column}) DO UPDATE SET premium_until = excluded.premium_until",
            target_id,
            until,
        )
        return until

    async def revoke(self, table, target_id):
        column = OWNERS[table]
        await self.run(f"UPDATE {table} SET premium_until = 0 WHERE {column} = ?", target_id)

    async def user_premium(self, user_id):
        return await self.user_value(user_id, "premium_until", 0)

    async def guild_premium(self, guild_id):
        return await self.guild_value(guild_id, "premium_until", 0)
