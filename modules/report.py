import requests
from datetime import datetime

def get_profit_report():
    try:
        res = requests.get("https://btc-daily-report.onrender.com/profit")
        res.raise_for_status()
        data = res.json()
        return data
    except Exception as e:
        return {"error": str(e)}

def format_profit_report_text(data):
    if "error" in data:
        return f"❌ 오류 발생: {data['error']}"

    return (
        f"📈 현재 포지션: {data.get('position', '정보 없음')}\n"
        f"💰 실현 손익: {data.get('realized_pnl', 'N/A')}\n"
        f"📉 미실현 손익: {data.get('unrealized_pnl', 'N/A')}\n"
        f"💹 총 손익: {data.get('total_pnl', 'N/A')}\n"
        f"📊 BTC 현재가 (Coinbase): {data.get('btc_price', 'N/A')}\n"
        f"🕓 분석 시각: {data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )

def get_prediction_report():
    return "📊 예측 리포트 기능은 아직 준비 중입니다."
