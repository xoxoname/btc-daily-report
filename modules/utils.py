# modules/utils.py
import requests
from datetime import datetime, timezone, timedelta

# 실시간 BTC 데이터 수집 (예: Render API, Coinbase 등)
async def fetch_realtime_data():
    try:
        r = requests.get("https://btc-daily-report.onrender.com/report")
        data = r.json()
        return data
    except Exception as e:
        return {\            'price': 0,
            'entry_price': 0,
            'unrealized': 0,
            'realized': 0,
            'pnl_percent': 0,
            'initial': 0,
            'current': 0,
            'total_profit': 0,
            'news_summary': '실시간 데이터 수집 실패.',
            'tech_summary': '-',
            'sentiment_summary': '-',
            'exception_summary': '-',
            'backtest_result': '-',
            'news_grade': '중립',
            'tech_grade': '중립',
            'sentiment_grade': '중립',
            'forecast_up': 0,
            'forecast_side': 0,
            'forecast_down': 0,
            'range_low': 0,
            'range_high': 0,
            'gpt_signal': '-',
            'schedule': '정보 없음',
            'comment': '데이터 오류로 리포트를 제공할 수 없습니다.'
        }

def krw(usd):
    rate = 1350  # 환율은 실제 API로 대체 가능
    return f"{int(float(usd) * rate):,}원"

def get_now_kst():
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    return now_kst.strftime("%Y-%m-%d %H:%M")
