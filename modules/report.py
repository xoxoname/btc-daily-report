from modules.data_fetch import fetch_btc_price

def format_profit_report_text():
    btc_data = fetch_btc_price()
    if "price" not in btc_data:
        return "❌ 비트코인 실시간 가격 조회에 실패했습니다."

    price = btc_data["price"]
    change = btc_data["change_percent"]
    high = btc_data["high_24h"]
    low = btc_data["low_24h"]

    report = f"""📊 *BTC 실시간 요약*
- 현재가: ${price:,.2f}
- 24H 최고가: ${high:,.2f}
- 24H 최저가: ${low:,.2f}
- 24H 변동률: {change:.2f}%

🚨 수익 정보는 아직 비트겟 연동이 활성화되지 않았습니다.
(비트겟 API Key가 등록되면 자동으로 실현/미실현 손익 리포트가 표시됩니다.)
"""

    return report

def get_prediction_report():
    # GPT 분석은 GPT 앱 내에서 수행되므로 코드 내에 없음
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."
