import os
import nest_asyncio
import asyncio
from modules.telegram import run_telegram_bot

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(run_telegram_bot())
