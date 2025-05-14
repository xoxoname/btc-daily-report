import requests
import hmac
import hashlib
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Bitget API credentials
API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def sign_request(timestamp, method, request_path, body=""):
    message = f"{timestamp}{method}{request_path}{body}"
    signature = hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return signature

def get_deposit_records():
    """Bitget API를 통해 누적 입금 내역 가져오기"""
    path = "/api/v2/spot/account/transferRecords"
    timestamp = get_timestamp()
    query = "?fromType=6&limit=100"  # fromType 6은 입금
    full_path = path + query
    signature = sign_request(timestamp, "GET", full_path)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

    response = requests.get(BASE_URL + full_path, headers=headers)
    if response.status_code != 200:
        raise Exception(f"입금 내역 조회 실패: {response.status_code} {response.text}")
    
    data = response.json()
    deposit_amounts = [
        float(record["amount"]) for record in data["data"] if record["fromType"] == "6"
    ]
    return sum(deposit_amounts)

def generate_report():
    # 실입금액 가져오기
    try:
        total_deposit = get_deposit_records()
    except Exception as e:
        total_deposit = None
        print(f"[경고] 입금 내역 조회 실패: {e}")

    # 실시간 BTC 가격 (예시용 - 실제 Coinbase API 또는 다른 가격 API 연결 필요)
    current_btc_price = 64000.0  # 임시 고정값

    # 예시 포트폴리오 수익 데이터 (실제 사용 시 Bitget PnL API와 연동)
    total_assets = 24500.0
    unrealized_pnl = 2200.0
    realized_pnl = 2300.0

    if total_deposit is not None:
        total_pnl = total_assets - total_deposit
        pnl_rate = (total_pnl / total_deposit) * 100
    else:
        total_pnl = pnl_rate = None

    # 출력 예시
    print("\n📊 [총 수익 리포트]")
    print(f"- 실입금 총액: {total_deposit:.2f} USDT" if total_deposit else "- 실입금 총액: 조회 실패")
    print(f"- 실현 수익: +{realized_pnl:.2f} USDT")
    print(f"- 미실현 수익: +{unrealized_pnl:.2f} USDT")
    print(f"- 현재 총 자산: {total_assets:.2f} USDT")
    if total_deposit:
        print(f"\n🧮 총 수익: +{total_pnl:.2f} USDT (📈 {pnl_rate:.2f}%)")
    print(f"\n📅 리포트 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 리포트 실행 (정해진 시간대에 Render에서 실행되도록 스케줄링)
if __name__ == "__main__":
    generate_report()
