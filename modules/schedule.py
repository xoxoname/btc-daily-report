import schedule
import asyncio
from modules.telegram_bot import send_report, send_exception

def job_send_report():
    asyncio.run(send_report())

def job_send_exception():
    asyncio.run(send_exception())

def start_schedulers(loop):
    schedule.every().day.at("09:00").do(job_send_report)
    schedule.every().day.at("13:00").do(job_send_report)
    schedule.every().day.at("17:00").do(job_send_report)
    schedule.every().day.at("23:00").do(job_send_report)
    schedule.every(5).minutes.do(job_send_exception)
    import threading
    def run():
        while True:
            schedule.run_pending()
    t = threading.Thread(target=run, daemon=True)
    t.start()
