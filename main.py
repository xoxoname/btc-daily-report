import asyncio
import sys

from modules.telegram import run_telegram_bot

if __name__ == "__main__":
    try:
        asyncio.run(run_telegram_bot())
    except RuntimeError as e:
        # Render 등에서 이미 루프 실행중일 경우
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        if sys.version_info >= (3, 7):
            loop.create_task(run_telegram_bot())
            loop.run_forever()
        else:
            loop.run_until_complete(run_telegram_bot())
