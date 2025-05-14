import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

# 1) 환경변수 로드 (Render 환경변수 또는 로컬 .env)
load_dotenv()
API_KEY    = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL   = "https://api.bitget.com"

# 2) 시그니처 생성
def make_signature(timestamp: str, method: str, request_path: str, body: str = "") -> str:
    message = timestamp + method.upper() + request_path + body
    return hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

# 3) 오늘 실현 PNL 조회 (v2 Mix account)
def fetch_realized_pnl():
    now = int(time.time() * 1000)
    # 한국시간 00:00 를 UTC로 변환
    today_9 = datetime.now(timezone(timedelta(hours=9))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = int(today_9.astimezone(timezone.utc).timestamp() * 1000)

    path  = "/api/v2/mix/account/get-account-bills"
    query = (
        f"?productType=UMCBL"
        f"&marginCoin=USDT"
        f"&startTime={start}"
        f"&endTime={now}"
        f"&pageNo=1"
        f"&pageSize=100"
    )
    ts  = str(int(time.time() * 1000))
    sig = make_signature(ts, "GET", path + query)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "ACCESS-SIGN": sig,
        "Content-Type": "application/json"
    }

    resp = requests.get(BASE_URL + path + query, headers=headers)
    resp.raise_for_status()
    bills = resp.json().get("data", [])
    return sum(item.get("realizedPnl", 0) for item in bills)

# 4) 실시간 오픈 포지션 조회 (v2 Mix position)
def fetch_open_positions():
    path  = "/api/v2/mix/position/get-open-positions"
    query = "?productType=UMCBL"
    ts    = str(int(time.time() * 1000))
    sig   = make_signature(ts, "GET", path + query)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "ACCESS-SIGN": sig,
        "Content-Type": "application/json"
    }

    resp = requests.get(BASE_URL + path + query, headers=headers)
    resp.raise_for_status()
    return resp.json().get("data", [])

# 5) 메인
def main():
    # 5-1) 오늘 실현 PNL 출력
    try:
        pnl = fetch_realized_pnl()
        print(f"📈 [오늘 실현 PNL] ${pnl:.2f}")
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")

    # 5-2) 실시간 미실현 PNL 출력
    print("📈 [실시간 포지션 수익 요약]")
    try:
        positions = fetch_open_positions()
        if not positions:
            print("📭 현재 보유 중인 포지션이 없습니다.")
        else:
            for p in positions:
                symbol = p.get("symbol")
                upnl   = float(p.get("unrealizedPnl", 0))
                print(f"• {symbol}: 미실현 PNL = ${upnl:+.2f}")
    except Exception as e:
        print(f"❌ 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
