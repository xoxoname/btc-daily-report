import threading
from modules.telegram_bot import run_telegram_bot
from scheduler.jobs import start_scheduler

if __name__ == "__main__":
    # 텔레그램 봇은 메인스레드(이벤트루프)에서 실행!
    threading.Thread(target=start_scheduler, daemon=True).start()
    run_telegram_bot()   # asyncio.run() 내부에서 동작
