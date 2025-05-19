
import os
import requests
from datetime import datetime

def send_auto_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"📡 GPT 매동 예측 분석 리포트\n📅 기준 시각: {now} (KST)\n━━━━━━━━━━━━━━━━━━━\n✅ 테스트 메시지입니다. 시스템은 정상 작동 중입니다.\n━━━━━━━━━━━━━━━━━━━"
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message}
        )
