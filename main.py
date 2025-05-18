import schedule
import time
from modules.report import generate_full_report
from modules.telegram import send_report

def job():
    report = generate_full_report()
    send_report(report)

schedule.every(5).minutes.do(job)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)