import schedule
import asyncio
from modules.telegram_bot import send_report, send_exception
from modules.utils import kr_now_str

# 정규 리포트 전송
def job_send_report():
    asyncio.run(send_report())

# 예외 감지 (5분마다)
def job_send_exception():
    asyncio.run(send_exception())

def start_schedulers(loop):
    schedule.every().day.at("09:00").do(job_send_report)
    schedule.every().day.at("13:00").do(job_send_report)
    schedule.every().day.at("17:00").do(job_send_report)
    schedule.every().day.at("23:00").do(job_send_report)
    schedule.every(5).minutes.do(job_send_exception)
    # 별도의 thread로 실행 (blocking 방지)
    import threading
    def run():
        while True:
            schedule.run_pending()
    t = threading.Thread(target=run, daemon=True)
    t.start()
