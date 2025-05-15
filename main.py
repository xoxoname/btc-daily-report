import os
import threading
from flask import Flask, jsonify
from dotenv import load_dotenv
import ccxt
import openai
from telegram import Bot

# Load environment variables from .env (if present)
load_dotenv()

# Required environment variables
BITGET_APIKEY   = os.environ['BITGET_APIKEY']
BITGET_PASSPHRASE = os.environ['BITGET_PASSPHRASE']
BITGET_SECRET   = os.environ['BITGET_SECRET']
CHAT_ID         = os.environ['CHAT_ID']
OPENAI_API_KEY  = os.environ['OPENAI_API_KEY']
TELEGRAM_TOKEN  = os.environ['TELEGRAM_TOKEN']
# Optional: an external report URL if you need to reference it
REPORT_URL      = os.environ.get('REPORT_URL')

# Initialize clients
openai.api_key = OPENAI_API_KEY
bot = Bot(token=TELEGRAM_TOKEN)

app = Flask(__name__)

# In-memory cache of report status
_report_status = {
    'started': False,
    'status': 'pending',  # 'pending' or 'ready'
    'data': None
}

# Function to fetch BTC data from Bitget
def fetch_bitget_ticker():
    exchange = ccxt.bitget({
        'apiKey': BITGET_APIKEY,
        'secret': BITGET_SECRET,
        'password': BITGET_PASSPHRASE,
    })
    return exchange.fetch_ticker('BTC/USDT')

# Background job: generate report, send Telegram, cache data
def generate_report():
    global _report_status
    try:
        ticker = fetch_bitget_ticker()
        price = ticker['last']

        # Build prompt for OpenAI
        prompt = f"BTC current price is {price}. Write a concise daily crypto report."
        resp = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=200
        )
        summary = resp.choices[0].message.content.strip()

        # Send to Telegram
        message = f"*Daily BTC Report*\nPrice: {price}\n\n{summary}"
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"Error generating or sending report: {e}")
        summary = None
        price = None

    # Update status and data
    _report_status['data'] = {
        'price': price,
        'summary': summary,
        'report_url': REPORT_URL
    }
    _report_status['status'] = 'ready'

# Health-check endpoint
@app.route('/')
def health_check():
    return jsonify({'status':'ok','message':'Service is up'}), 200

# Report endpoint
@app.route('/report', methods=['GET'])
def report():
    global _report_status
    # First trigger: start background job
    if not _report_status['started']:
        _report_status['started'] = True
        threading.Thread(target=generate_report, daemon=True).start()
        return jsonify(
            status='pending',
            message='Report is being generated. Please retry in a minute.'
        ), 200

    # Still generating
    if _report_status['status'] == 'pending':
        return jsonify(
            status='pending',
            message='Report is being generated. Please retry in a minute.'
        ), 200

    # Ready
    return jsonify(
        status='ready',
        message='Report ready',
        data=_report_status['data']
    ), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
