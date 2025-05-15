# 🔧 유틸리티 함수 모음

from datetime import datetime

def get_krw_from_usd(usd_amount, rate=1380):
    return int(usd_amount * rate)

def get_now_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
