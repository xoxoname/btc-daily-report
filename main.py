import threading
from modules.telegram_bot import run_telegram_bot
import schedule
import time

def schedule_jobs():
    from modules.reporter import send_scheduled_reports
    schedule.every().day.at("09:00").do(send_scheduled_reports)
    schedule.every().day.at("13:00").do(send_scheduled_reports)
    schedule.every().day.at("17:00").do(send_scheduled_reports)
    schedule.every().day.at("23:00").do(send_scheduled_reports)
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    t1 = threading.Thread(target=run_telegram_bot)
    t2 = threading.Thread(target=schedule_jobs)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
