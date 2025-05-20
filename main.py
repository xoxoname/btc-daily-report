import asyncio
from modules.telegram import run_telegram_bot

if __name__ == "__main__":
    try:
        asyncio.run(run_telegram_bot())
    except RuntimeError as e:
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.create_task(run_telegram_bot())
        loop.run_forever()
