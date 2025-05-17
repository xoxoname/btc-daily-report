from modules.report import generate_profit_report
from modules.schedule import get_upcoming_events
from modules.utils import send_telegram_message, get_current_timestamp

def handle_command(data):
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    if text == "/수익":
        send_telegram_message(chat_id, generate_profit_report())
    elif text == "/일정":
        events = get_upcoming_events()
        event_text = "\n".join([f"{date}\t{event}\t{impact}" for date, event, impact in events])
        msg = f"📅 향후 7일간 주요 일정 (/일정 명령어 예시)

{event_text}"
        send_telegram_message(chat_id, msg)
    else:
        send_telegram_message(chat_id, "알 수 없는 명령어입니다.")