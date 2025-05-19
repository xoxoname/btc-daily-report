import schedule
import time

def run_scheduled_jobs():
    schedule.every(5).minutes.do(lambda: print("예외 상황 감지 실행 중..."))
    schedule.every().day.at("09:00").do(lambda: print("정규 리포트 전송"))
    while True:
        schedule.run_pending()
        time.sleep(1)
