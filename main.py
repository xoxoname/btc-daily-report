import os
import json
from datetime import datetime

from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import ccxt
import openai
from telegram import Bot

# Load environment variables
BITGET_API_KEY = os.getenv('BITGET_API_KEY')
BITGET_SECRET = os.getenv('BITGET_SECRET')
BITGET_PASSPHRASE = os.getenv('BITGET_PASSPHRASE')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Initialize services
exchange = ccxt.bitget({
    'apiKey': BITGET_API_KEY,
    'secret': BITGET_SECRET,
    'password': BITGET_PASSPHRASE,
    'enableRateLimit': True,
    'timeout': 10000,  # ms
})
openai.api_key = OPENAI_API_KEY
bot = Bot(TELEGRAM_TOKEN)

app = Flask(__name__)
REPORT_FILE = '/tmp/latest_report.json'


def generate_report():
    """
    Fetch BTC/USDT daily OHLCV, send analysis to OpenAI,
    cache report locally, and notify via Telegram.
    """
    try:
        # 1-week daily OHLCV
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1d', limit=7)
        # Prepare prompt
        rows = '\n'.join(','.join(map(str, r)) for r in ohlcv)
        prompt = f"Analyze the following BTC/USDT daily OHLCV data (timestamp,open,high,low,close,volume):\n{rows}"
        # Call OpenAI
        completion = openai.ChatCompletion.create(
            model='gpt-4o-mini',
            messages=[{'role': 'system', 'content': 'You are a crypto analyst.'},
                      {'role': 'user', 'content': prompt}]
        )
        analysis = completion.choices[0].message.content

        # Build report
        report = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'ohlcv': ohlcv,
            'analysis': analysis
        }
        # Cache to local file
        with open(REPORT_FILE, 'w') as f:
            json.dump(report, f)

        # Send via Telegram
        bot.send_message(chat_id=CHAT_ID, text=analysis)
    except Exception as e:
        app.logger.exception('Report generation failed')
        # Notify failure
        try:
            bot.send_message(chat_id=CHAT_ID, text=f'Report failed: {e}')
        except Exception:
            app.logger.exception('Telegram notification failed')


@app.route('/report')
def report_endpoint():
    """Return latest cached report, or a 202 if pending."""
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE) as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify({
            'status': 'pending',
            'message': 'Report is being generated. Please retry in a minute.'
        }), 202


if __name__ == '__main__':
    # Scheduler to run daily at 00:00 UTC and once on startup
    scheduler = BackgroundScheduler()
    scheduler.add_job(generate_report, 'cron', hour=0, minute=0)
    scheduler.add_job(generate_report, 'date', run_date=datetime.utcnow())
    scheduler.start()

    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
