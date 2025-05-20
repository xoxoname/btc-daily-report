from modules.telegram_bot import run_telegram_bot
from modules.schedule import start_schedulers

if __name__ == "__main__":
    start_schedulers()   # 인자 필요 없음
    run_telegram_bot()
