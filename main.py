import os
import ccxt
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables (Render sets these automatically)
load_dotenv()

# Initialize Bitget futures client via ccxt
exchange = ccxt.bitget({
    'apiKey':       os.getenv('BITGET_API_KEY', ''),
    'secret':       os.getenv('BITGET_API_SECRET', ''),
    'password':     os.getenv('BITGET_API_PASSPHRASE', ''),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    },
})

app = Flask(__name__)

# Store last report data and initial equity for % calculation
data_store = {
    'initial_equity': None,
    'last': {}
}


def fetch_report():
    """
    Fetch current equity, unrealized and realized PnL, cumulative PnL, and today's % change.
    """
    bal = exchange.fetch_balance({'type': 'future'})
    equity = float(bal['total'].get('USDT', 0))
    # Initialize baseline
    if data_store['initial_equity'] is None:
        data_store['initial_equity'] = equity
    # Calculate % change since baseline
    pct_change = (equity - data_store['initial_equity']) / data_store['initial_equity'] * 100

    # Fetch positions
    positions = exchange.fetch_positions()
    # Sum unrealized PnL for BTC/USDT pair
    unrealized = 0.0
    for pos in positions:
        if pos['symbol'] == 'BTC/USDT':
            unrealized += float(pos.get('unrealizedPnl', 0))
    # Realized PnL = (current equity - baseline) - unrealized
    realized_today = (equity - data_store['initial_equity']) - unrealized
    cumulative = equity - data_store['initial_equity']

    # Prepare report
    report = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'equity_usdt': round(equity, 4),
        'percent_change': round(pct_change, 2),
        'realized_today': round(realized_today, 4),
        'unrealized_pnl': round(unrealized, 4),
        'cumulative_pnl': round(cumulative, 4),
    }
    data_store['last'] = report
    return report

# Background scheduler: run every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_report, 'interval', minutes=5)
scheduler.start()

@app.route('/report')
def report_endpoint():
    """HTTP endpoint to get the latest PnL report (runs on demand)."""
    report = fetch_report()
    return jsonify(report)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
