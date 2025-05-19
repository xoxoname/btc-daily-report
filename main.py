import threading
from modules.telegram_bot import run_telegram_bot
from scheduler.jobs import start_scheduler

if __name__ == "__main__":
    threading.Thread(target=start_scheduler, daemon=True).start()
    run_telegram_bot()
