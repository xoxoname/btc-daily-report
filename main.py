import asyncio
from modules.telegram_bot import run_telegram_bot
from modules.schedule import start_schedulers

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_telegram_bot())
    start_schedulers(loop)
    loop.run_forever()
