import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from utils import emoji_sync


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not config.TOKEN:
        print("TOKEN is missing in .env")
        return
    uploaded = await emoji_sync.sync(config.TOKEN)
    print(f"Mapped {len(uploaded)} emojis into {config.EMOJIS_UPLOADED_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())
