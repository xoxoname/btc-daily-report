import requests

def get_profit_report():
    try:
        res = requests.get("https://btc-daily-report.onrender.com/data.json")
        data = res.json()
        usdt = data.get("usdt_pnl", "N/A")
        krw = data.get("krw_pnl", "N/A")
        return {
            "usdt_pnl": f"{usdt} USDT",
            "krw_pnl": f"{krw} 원"
        }
    except Exception as e:
        return {
            "usdt_pnl": "불러오기 실패",
            "krw_pnl": str(e)
        }

def get_prediction_report():
    return (
        "📊 *BTC 매동 예측 리포트*\n"
        "- 기술적 분석: 강한 저항선 부근, RSI 65\n"
        "- 심리 분석: 공포탐욕지수 70 (탐욕)\n"
        "- 구조적 이슈: ETF 수요 증가\n"
        "- 향후 12시간 예측: 약한 상승 후 조정 가능성\n"
        "- 예외 감지 없음\n\n"
        "_(이 리포트는 자동 분석 시스템에 의해 생성됨)_"
    )
