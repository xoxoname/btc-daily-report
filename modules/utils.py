import requests
import os
from modules.constants import REPORT_URL

def fetch_report_data():
    try:
        response = requests.get(REPORT_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("❌ 리포트 데이터 불러오기 실패:", e)
        return {
            "summary": "데이터를 불러오는 데 실패했습니다.",
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "total_asset": 0,
            "return_rate": 0,
        }
