from modules.utils import send_telegram_message
import os

def build_and_send_report():
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    message = "🧾 자동 스케줄링 리포트입니다.\n\n(자산 및 분석 내용은 추후 삽입)"
    send_telegram_message(chat_id, message)
