# modules/utils.py

import requests

def fetch_coinbase_price():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        data = response.json()
        return float(data["data"]["amount"])
    except Exception as e:
        print(f"[가격 조회 실패]: {e}")
        return None

def fetch_bitget_position_data():
    # 실제 API 연동 시 이 부분을 수정
    # 테스트용 mock 데이터
    return {
        "entry_value": 1000.00,
        "pnl": 80.00
    }

def fetch_latest_event_summary_kr():
    # 추후 GPT API 연동 후 실제 뉴스를 요약
    return "트럼프 발언 / 미국 CPI 발표 등 주요 이벤트 확인됨."

def format_currency(value):
    return f"{value:,.2f}"
