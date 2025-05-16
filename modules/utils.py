import os
import requests
from datetime import datetime
from pytz import timezone
from modules.bitget_api import fetch_bitget_positions, fetch_bitget_wallet_balance

def get_kst_now():
    return datetime.now(timezone("Asia/Seoul"))

def send_telegram_message(chat_id, text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)

def get_command_text(command_type):
    if command_type == "profit":
        balance = fetch_bitget_wallet_balance()
        positions = fetch_bitget_positions()
        return f"💰 총자산: {balance['total_equity']} USDT\n📈 포지션 수익: {positions}"
    elif command_type == "prediction":
        return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."
    elif command_type == "schedule":
        return "🗓 주요 경제 일정 분석 준비중입니다."
    else:
        return "알 수 없는 명령어입니다."
