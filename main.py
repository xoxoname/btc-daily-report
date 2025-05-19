import threading
from modules.telegram_bot import run_telegram_bot
from scheduler.jobs import start_scheduler

if __name__ == "__main__":
    # 스케줄러를 먼저 백그라운드에서 실행 (동기 방식)
    threading.Thread(target=start_scheduler, daemon=True).start()
    # 텔레그램 봇만 메인에서 바로 실행(비동기 run_polling만 사용)
    run_telegram_bot()
