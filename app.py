import os
import schedule
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from modules.exchange import BitgetAPI
from modules.analyst import GPTForecaster
from modules.telegram import TelegramBot

load_dotenv()

def get_kst_now():
    return datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Asia/Seoul"))

class ForecastBot:
    def __init__(self):
        self.exchange = BitgetAPI(
            api_key=os.getenv('BITGET_APIKEY'),
            secret=os.getenv('BITGET_APISECRET'),
            passphrase=os.getenv('BITGET_PASSPHRASE')
        )
        self.analyst = GPTForecaster(os.getenv('OPENAI_API_KEY'))
        self.bot = TelegramBot(
            token=os.getenv('TELEGRAM_BOT_TOKEN'),
            chat_id=os.getenv('TELEGRAM_CHAT_ID')
        )

    def kst_schedule(self):
        schedule.every().day.at("09:00").do(self.generate_report)
        schedule.every().day.at("13:00").do(self.generate_report)
        schedule.every().day.at("17:00").do(self.generate_report)
        schedule.every().day.at("23:00").do(self.generate_report)

    def generate_report(self):
        try:
            market_data = self.exchange.get_market_data()
            funding = self.exchange.get_funding_rate()
            oi_data = self.exchange.get_open_interest()
            now = get_kst_now().strftime("%Y-%m-%d %H:%M (KST)")

            analysis = self.analyst.analyze(
                price=market_data['price'],
                funding_rate=funding,
                oi_change=oi_data['change'],
                volume=market_data['volume'],
                report_time=now
            )
            self.bot.send_report(analysis)
        except Exception as e:
            error_msg = f"🚨 리포트 생성 실패: {str(e)}"
            self.bot.send_alert(error_msg)

    def run(self):
        self.kst_schedule()
        print("⏰ 비트코인 자동 예측 봇 실행 중...")
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    bot = ForecastBot()
    bot.run()
