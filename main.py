from modules.telegram_bot import start_telegram_bot
from scheduler.jobs import start_scheduler

if __name__ == "__main__":
    # 텔레그램 봇(명령어 응답) 및 스케줄러(정규/예외 감지) 병렬 실행
    import threading
    threading.Thread(target=start_telegram_bot, daemon=True).start()
    start_scheduler()
