# 📁 src/main.py

import asyncio
from modules.telegram_bot import application

if __name__ == "__main__":
    print("✅ 텔레그램 봇 실행 시작됨")
    asyncio.run(application.run_polling(
        allowed_updates=application.bot.allowed_updates,
        close_loop=False
    ))
