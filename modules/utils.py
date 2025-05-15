import requests
import logging
from modules.constants import TELEGRAM_TOKEN

def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })
    if resp.status_code != 200:
        logging.error(f"Telegram 전송 실패 ({resp.status_code}): {resp.text}")
