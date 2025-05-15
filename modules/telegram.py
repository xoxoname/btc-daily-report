from modules.constants import CHAT_ID
from modules.report import format_profit_report_text, build_and_send_report
from modules.report import send_telegram_message

def process_telegram_message(data):
    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"]["text"].strip()

    if chat_id != CHAT_ID:
        send_telegram_message(chat_id, "접근이 제한된 사용자입니다.")
        return

    if text == "/수익":
        send_telegram_message(chat_id, format_profit_report_text())
    elif text == "/예측":
        build_and_send_report()
    elif text == "/일정":
        send_telegram_message(chat_id, "⏰ 매일 09시 / 13시 / 23시에 리포트 자동 전송됩니다.")
    else:
        send_telegram_message(chat_id, "사용 가능한 명령어: /수익 /예측 /일정")
