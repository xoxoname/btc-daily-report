import asyncio
from modules.telegram import run_telegram_bot

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(run_telegram_bot())
    except KeyboardInterrupt:
        print("🚨 종료됨: 수동 종료 감지")
    except Exception as e:
        print(f"🚨 예외 발생: {e}")