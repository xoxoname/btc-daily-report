import schedule
import threading
from modules.telegram_bot import send_report, send_exception

def job_send_report():
    send_report()

def job_send_exception():
    send_exception()

def start_schedulers():
    schedule.every().day.at("09:00").do(job_send_report)
    schedule.every().day.at("13:00").do(job_send_report)
    schedule.every().day.at("17:00").do(job_send_report)
    schedule.every().day.at("23:00").do(job_send_report)
    schedule.every(5).minutes.do(job_send_exception)

    def run():
        while True:
            schedule.run_pending()
    t = threading.Thread(target=run, daemon=True)
    t.start()
