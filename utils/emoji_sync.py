import asyncio
import base64
import json
import logging

import aiohttp

import config

API = "https://discord.com/api/v10"
CDN = "https://cdn.discordapp.com/emojis/{id}.{ext}?size=128&quality=lossless"
LOCAL_EXTENSIONS = ("png", "gif", "webp", "jpg", "jpeg")
MIME = {"png": "image/png", "gif": "image/gif", "webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg"}

log = logging.getLogger("emoji_sync")


async def request(session, method, path, token, **kwargs):
    headers = {"Authorization": f"Bot {token}"}
    for _ in range(5):
        async with session.request(method, f"{API}{path}", headers=headers, **kwargs) as response:
            if response.status == 429:
                data = await response.json()
                await asyncio.sleep(float(data.get("retry_after", 1)) + 0.25)
                continue
            if response.status >= 400:
                return response.status, await response.text()
            return response.status, await response.json()
    return 429, "rate limited"


def local_image(name):
    for extension in LOCAL_EXTENSIONS:
        path = config.EMOJI_LOCAL_DIR / f"{name}.{extension}"
        if path.exists():
            return path.read_bytes(), extension
    return None


async def download(session, entry):
    source = entry.get("source")
    if not source:
        return None
    extension = "gif" if entry.get("animated") else "png"
    async with session.get(CDN.format(id=source, ext=extension)) as response:
        if response.status != 200:
            return None
        return await response.read(), extension


async def sync(token, session=None):
    own_session = session is None
    session = session or aiohttp.ClientSession()
    try:
        entries = json.loads(config.EMOJIS_FILE.read_text(encoding="utf-8"))
        status, app = await request(session, "GET", "/applications/@me", token)
        if status != 200:
            log.error("Could not read application info: %s", app)
            return {}
        app_id = app["id"]
        status, listing = await request(session, "GET", f"/applications/{app_id}/emojis", token)
        existing = {item["name"]: item for item in listing.get("items", [])} if status == 200 else {}
        uploaded = {}
        created = 0
        for key, entry in entries.items():
            name = entry["name"]
            item = existing.get(name)
            if item is None:
                image = local_image(name) or await download(session, entry)
                if image is None:
                    continue
                data, extension = image
                payload = {
                    "name": name,
                    "image": f"data:{MIME[extension]};base64,{base64.b64encode(data).decode()}",
                }
                status, item = await request(session, "POST", f"/applications/{app_id}/emojis", token, json=payload)
                if status not in (200, 201):
                    log.warning("Upload failed for %s: %s", name, item)
                    continue
                existing[name] = item
                created += 1
            uploaded[key] = {
                "id": str(item["id"]),
                "name": item["name"],
                "animated": bool(item.get("animated")),
            }
        config.EMOJIS_UPLOADED_FILE.write_text(json.dumps(uploaded, indent=2), encoding="utf-8")
        log.info("Emoji sync finished: %s mapped, %s created", len(uploaded), created)
        return uploaded
    finally:
        if own_session:
            await session.close()
