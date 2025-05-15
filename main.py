# main.py
import os
import logging
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import ccxt
import openai
import requests
from dotenv import load_dotenv

# 리포트 포맷팅 모듈
from modules.report import (
    get_profit_report,
    format_profit_report_text,
    get_prediction_report,
    format_prediction_report_text,
)

# 환경 변수 로드
load_dotenv()
BITGET_API_KEY    = os.getenv('BITGET_API_KEY')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
BITGET_SECRET     = os.getenv('BITGET_SECRET')
OPENAI_API_KEY    = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_TOKEN')
CHAT_ID           = os.getenv('CHAT_ID')  # 숫자만
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
    return resp.choices[0].message.content.strip()

def send_telegram(full_text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning("텔레그램 토큰 또는 CHAT_ID가 설정되어 있지 않습니다.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id':    CHAT_ID,
        'text':       full_text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True,
    }
    r = requests.post(url, json=payload)
    try:
        r.raise_for_status()
        logging.info("Sent Telegram message.")
    except Exception as e:
        logging.error(f"텔레그램 전송 실패: {e} - {r.text}")

def create_report():
    price = None
    summary = None

    # 1) 가격 fetch
    try:
        price = fetch_price()
        logging.info(f"Fetched BTC price: {price}")
    except Exception as e:
        logging.error(f"Error fetching price: {e}")

    # 2) 한줄 요약
    if price is not None:
        try:
            summary = generate_summary(price)
            logging.info("Generated summary.")
        except Exception as e:
            logging.error(f"Error generating summary: {e}")
            summary = None

    # 3) 수익 리포트
    profit_data = get_profit_report()
    profit_text = format_profit_report_text(profit_data)

    # 4) 예측 리포트
    pred_data = get_prediction_report()
    pred_text = format_prediction_report_text(pred_data)

    # 5) Telegram에 보낼 풀 메시지 조합
    full_text = (
        "*📊 Bitcoin Daily Report*\n\n"
        f"*1) 현재 가격:* `{price or 'N/A'}` USD\n"
        f"*2) 한줄 요약:* {summary or '생성 실패'}\n\n"
        f"*💰 실현+미실현 손익 보고서*\n{profit_text}\n\n"
        f"*🔮 BTC 예측 보고서*\n{pred_text}"
    )
    send_telegram(full_text)

    # 6) HTTP API 응답
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
