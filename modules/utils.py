# 유틸 함수 모듈
def calculate_krw(usdt_amount, exchange_rate=1350):
    return round(usdt_amount * exchange_rate, 1)
