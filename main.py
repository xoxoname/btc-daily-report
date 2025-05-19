from scheduler.jobs import run_scheduled_jobs
from modules.telegram import start_telegram_bot

if __name__ == "__main__":
    start_telegram_bot()
    run_scheduled_jobs()
