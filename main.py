import os
import logging
from flask import Flask, jsonify
import ccxt
import openai
import requests
from dotenv import load_dotenv

# 1) 환경변수 로드
load_dotenv()
BITGET_API_KEY    = os.getenv('BITGET_API_KEY')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
BITGET_SECRET     = os.getenv('BITGET_SECRET')
OPENAI_API_KEY    = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
CHAT_ID           = os.getenv('CHAT_ID')            # ex) "-123456789" 또는 "@channelusername"
REPORT_URL        = os.getenv('REPORT_URL', '').rstrip('/')

# 2) REPORT_URL 에 /report 가 중복 들어온 경우 보정
if REPORT_URL.endswith('/report'):
    BASE_URL = REPORT_URL[:-7]
else:
    BASE_URL = REPORT_URL

# 3) OpenAI 초기화
openai.api_key = OPENAI_API_KEY

# 4) 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

app = Flask(__name__)

def fetch_price():
    exchange = ccxt.bitget({
        'apiKey':   BITGET_API_KEY,
        'secret':   BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
    })
    ticker = exchange.fetch_ticker('BTC/USDT')
    return ticker.get('last')

def generate_summary(price: float) -> str:
    prompt = f"현재 Bitcoin 가격이 {price} USD 입니다. 이 가격에 대한 간단한 한 문장 요약을 만들어 주세요."
    resp = openai.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{"role":"user","content":prompt}],
        max_tokens=60,
        temperature=0.5,
    )
    return resp.choices[0].message['content'].strip()

def send_telegram(price, summary):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning("텔레그램 토큰 또는 CHAT_ID 미설정")
        return
    text = (
        f"*Bitcoin Daily Report*\n"
        f"Price: `{price}` USD\n"
        f"Summary: {summary}\n\n"
        f"[View full report]({BASE_URL}/report)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        'chat_id':    CHAT_ID,
        'text':       text,
        'parse_mode': 'Markdown'
    })
    try:
        resp.raise_for_status()
        logging.info("Sent Telegram message.")
    except Exception as e:
        logging.error(f"텔레그램 전송 실패: {e} - resp.text: {resp.text}")

def create_report():
    price = None
    summary = None

    # 가격 조회
    try:
        price = fetch_price()
        logging.info(f"Fetched BTC price: {price}")
    except Exception as e:
        logging.error(f"Error fetching price: {e}")

    # 요약 생성
    if price is not None:
        try:
            summary = generate_summary(price)
            logging.info("Generated summary.")
        except Exception as e:
            logging.error(f"Error generating summary: {e}")

    # 텔레그램 전송
    send_telegram(price, summary)

    return {
        'data': {
            'price':      price,
            'summary':    summary,
            'report_url': f"{BASE_URL}/report"
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
    # 배포 시: gunicorn main:app --bind 0.0.0.0:$PORT
    app.run(host='0.0.0.0', port=port)
