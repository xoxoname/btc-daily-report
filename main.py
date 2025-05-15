# main.py
import os
import logging
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import ccxt
import openai
import requests
from dotenv import load_dotenv

load_dotenv()

BITGET_API_KEY    = os.getenv('BITGET_API_KEY')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
BITGET_SECRET     = os.getenv('BITGET_SECRET')
OPENAI_API_KEY    = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
CHAT_ID           = os.getenv('CHAT_ID')  # 반드시 숫자로만 구성된 값
REPORT_URL        = os.getenv('REPORT_URL', '').rstrip('/')

openai.api_key = OPENAI_API_KEY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

app = Flask(__name__)

def fetch_price():
    exchange = ccxt.bitget({
        'apiKey':    BITGET_API_KEY,
        'secret':    BITGET_SECRET,
        'password':  BITGET_PASSPHRASE,
    })
    ticker = exchange.fetch_ticker('BTC/USDT')
    return ticker.get('last')

def generate_summary(price: float) -> str:
    prompt = f"현재 Bitcoin 가격이 {price} USD 입니다. 이 가격에 대한 간단한 한 문장 요약을 만들어 주세요."
    resp = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.5,
    )
    # v1 interface: choices[0].message.content
    return resp.choices[0].message.content.strip()

def send_telegram(price, summary):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning("텔레그램 토큰 또는 CHAT_ID가 설정되어 있지 않습니다.")
        return
    text = (
        f"*Bitcoin Daily Report*\n"
        f"Price: `{price}` USD\n"
        f"Summary: {summary or '요약 생성 실패'}\n\n"
        f"[View full report]({REPORT_URL}/report)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={
        'chat_id':    CHAT_ID,
        'text':       text,
        'parse_mode': 'Markdown'
    })
    try:
        r.raise_for_status()
    except Exception as e:
        logging.error(f"텔레그램 전송 실패: {e} - resp.text: {r.text}")

def create_report():
    price = None
    summary = None

    try:
        price = fetch_price()
        logging.info(f"Fetched BTC price: {price}")
    except Exception as e:
        logging.error(f"Error fetching price: {e}")

    if price is not None:
        try:
            summary = generate_summary(price)
            logging.info("Generated summary.")
        except Exception as e:
            logging.error(f"Error generating summary: {e}")

    try:
        send_telegram(price, summary)
        logging.info("Sent Telegram message.")
    except Exception as e:
        logging.error(f"텔레그램 전송 실패: {e}")

    return {
        'data': {
            'price':      price,
            'summary':    summary,
            'report_url': f"{REPORT_URL}/report"
        },
        'message': 'Report ready',
        'status':  'ready'
    }

@app.route('/report', methods=['GET'])
def report_endpoint():
    logging.info("Received /report request.")
    return jsonify(create_report())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
