import schedule
import time
from modules.exchange import fetch_bitget_account_info, fetch_bitget_positions
from modules.telegram import send_profit_report

def job():
    account_info = fetch_bitget_account_info()
    position_info = fetch_bitget_positions()
    report = f"💰 자동 수익 리포트\n잔고: {account_info}\n포지션: {position_info}"
    send_profit_report(report)

schedule.every(5).minutes.do(job)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)