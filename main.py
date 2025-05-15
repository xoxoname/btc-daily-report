# File: requirements.txt
```text
# Web service dependencies
flask==2.3.2
gunicorn==20.1.0
requests>=2.18.4
apscheduler==3.10.4
ccxt==4.4.82
openai==1.14.3
python-dotenv==1.0.1
beautifulsoup4
```  

# File: main.py
```python
import os
import logging
from datetime import datetime
import pytz
import requests
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from modules.report import (
    get_profit_report,
    format_profit_report_text,
    get_prediction_report,
    format_prediction_report_text,
)
from modules.schedule import (
    get_upcoming_events,
    format_schedule_text,
)

# Required env vars
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("CHAT_ID")     # Your Telegram chat ID, e.g. 1038440081
APP_URL        = os.getenv("APP_URL")     # e.g. https://btc-daily-report.onrender.com

# Logging config
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")
app = Flask(__name__)

# Telegram webhook registration
def register_webhook():
    if not TELEGRAM_TOKEN or not APP_URL:
        logging.warning("Missing TELEGRAM_TOKEN or APP_URL for webhook registration.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        resp = requests.post(url, json={"url": f"{APP_URL}/bot"})
        logging.info(f"Webhook set: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Failed to register webhook: {e}")

# Run once at startup
def _startup():
    register_webhook()
_scheduler = BackgroundScheduler()
_scheduler.start()
_startup()

# Helper to send Telegram messages
def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    })
    if resp.status_code != 200:
        logging.error(f"Telegram send failed ({resp.status_code}): {resp.text}")

# Build and send the comprehensive report
def create_full_report() -> str:
    kst = pytz.timezone("Asia/Seoul")
    now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
    header = f"📢 *GPT 매동 예측 예상*\n{now_str} 기준\n\n"

    profit = get_profit_report()
    profit_text = format_profit_report_text(profit)

    prediction = get_prediction_report()
    prediction_text = format_prediction_report_text(prediction)

    return header + profit_text + "\n\n" + prediction_text

# Handlers
def handle_report(chat_id: int):
    send_message(chat_id, "🔎 자료 검색 중… 잠시만 기다려주세요.")
    report_text = create_full_report()
    send_message(chat_id, report_text)

def handle_schedule(chat_id: int):
    send_message(chat_id, "🔎 일정 정보 수집 중… 잠시만 기다려주세요.")
    events = get_upcoming_events()
    schedule_text = format_schedule_text(events)
    send_message(chat_id, schedule_text)

# Automatic scheduled reports at 09:00, 13:00, 23:00 KST
scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=9,  minute=0)
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=13, minute=0)
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=23, minute=0)
scheduler.start()

# Web routes
@app.route("/", methods=["GET"])
def index():
    return jsonify({"status":"ok"})

@app.route("/bot", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    msg = update.get("message")
    if not msg:
        return "OK"
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text.startswith("/report") or "리포트" in text:
        handle_report(chat_id)
    elif text.startswith("/일정"):
        handle_schedule(chat_id)
    else:
        send_message(chat_id, "⚡️ 지원하는 명령어: /report, /일정")
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
```

# File: modules/report.py
```python
import os
import requests
import pytz
from datetime import datetime
import ccxt
import openai
from dotenv import load_dotenv

# Load env
load_dotenv()

# API keys
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
BITGET_API_KEY    = os.getenv("BITGET_API_KEY")
BITGET_SECRET     = os.getenv("BITGET_SECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
REPORT_URL        = os.getenv("REPORT_URL").rstrip("/")

openai.api_key = OPENAI_API_KEY

# 1) Profit report
def get_profit_report():
    try:
        resp = requests.get(f"{REPORT_URL}/report")
        return resp.json().get("data", {})
    except Exception as e:
        return {"error": str(e)}

def format_profit_report_text(data: dict) -> str:
    kst = pytz.timezone("Asia/Seoul")
    now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    usdt_pnl = data.get("usdt_pnl", "N/A")
    krw_pnl  = data.get("krw_pnl",  "N/A")
    return (
        f"[{now_str}]\n"
        f"💰 *실현+미실현 손익*\n"
        f"- {usdt_pnl} USDT\n"
        f"- 약 {krw_pnl} KRW"
    )

# 2) Prediction report via GPT
def get_prediction_report() -> str:
    # Fetch current BTC price
    price = None
    try:
        exchange = ccxt.bitget({
            'apiKey':    BITGET_API_KEY,
            'secret':    BITGET_SECRET,
            'password':  BITGET_PASSPHRASE,
        })
        ticker = exchange.fetch_ticker('BTC/USDT')
        price = ticker.get('last')
    except:
        pass

    # Build GPT prompt (customize with full detailed prompt)
    prompt = build_predict_prompt(price)
    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0.6,
    )
    return resp.choices[0].message.content

# Example prompt builder
def build_predict_prompt(price: float) -> str:
    return (
        "아래 항목을 실시간 데이터와 신뢰 가능한 자료 참고하여 분석하고,"
        "12시간 예측 전략 보고서를 작성하세요.\n"
        f"현재 BTC 가격: {price} USD\n"
        "1. 시장 이벤트...\n"
        "2. 기술 분석...\n"
        "3. 심리 지표...\n"
        "4. 예측 및 전략...\n"
        "5. 예외 감지 및 피드백 루프...\n"
    )

def format_prediction_report_text(text: str) -> str:
    return f"🔮 *BTC 예측 보고서*\n{text}"
```

# File: modules/schedule.py
```python
import requests
from bs4 import BeautifulSoup
import pytz
from datetime import datetime, timedelta

# Fetch upcoming crypto and US macro events (stub)
def get_upcoming_events():
    # TODO: 실제 일정 API나 스크래핑 구현
    return []

def format_schedule_text(events: list) -> str:
    kst = pytz.timezone('Asia/Seoul')
    header = "*📅 향후 1주일 주요 일정*\n"
    if not events:
        return header + "일정 정보가 없습니다."
    lines = []
    for ev in events:
        lines.append(f"- {ev['time']} {ev['title']} ({ev['impact']})")
    return header + "\n".join(lines)
