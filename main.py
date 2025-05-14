import os, time, hmac, hashlib, requests
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

# 1) 환경변수 로드
load_dotenv()
API_KEY     = os.getenv("BITGET_API_KEY")
SECRET_KEY  = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE  = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

# 2) 서명 생성 함수
def make_signature(timestamp: str, method: str, request_path: str, body: str = "") -> str:
    message = timestamp + method.upper() + request_path + body
    return hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()

# 3) 실현 PNL (accountBill) 조회
def fetch_realized_pnl():
    # 오늘 00:00 UTC+9 -> UTC 변환
    now = int(time.time() * 1000)
    today9 = datetime.now(timezone(timedelta(hours=9))).replace(hour=0, minute=0, second=0, microsecond=0)
    today0 = int(today9.astimezone(timezone.utc).timestamp() * 1000)

    path = "/api/mix/v1/account/accountBill"
    params = f"?productType=UMCBL&marginCoin=USDT&startTime={today0}&endTime={now}&pageSize=50"
    request_path = path + params

    timestamp = str(int(time.time() * 1000))
    signature = make_signature(timestamp, "GET", request_path)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
        "ACCESS-SIGN": signature
    }

    r = requests.get(BASE_URL + request_path, headers=headers)
    r.raise_for_status()
    data = r.json().get("data", [])
    # 수익 합산
    pnl_sum = sum(item.get("realizedPnl", 0) for item in data)
    return pnl_sum

# 4) 오픈 포지션 (all-position) 조회
def fetch_open_positions():
    path = "/api/mix/v1/position/all-position"
    params = "?productType=UMCBL&marginCoin=USDT"
    request_path = path + params

    timestamp = str(int(time.time() * 1000))
    signature = make_signature(timestamp, "GET", request_path)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
        "ACCESS-SIGN": signature
    }

    r = requests.get(BASE_URL + request_path, headers=headers)
    r.raise_for_status()
    positions = r.json().get("data", [])
    return positions

# 5) 메인 실행부
def main():
    # 5-1) 오늘 실현 PNL
    try:
        pnl = fetch_realized_pnl()
        print(f"📈 [오늘 실현 PNL] ${pnl:.2f}")
    except Exception as e:
        print(f"❌ 오늘 수익 데이터 조회 실패: {e}")

    # 5-2) 실시간 미실현 PNL (오픈 포지션)
    print("📈 [실시간 포지션 수익 요약]")
    try:
        pos = fetch_open_positions()
        if not pos:
            print("📭 현재 보유 중인 포지션이 없습니다.")
        else:
            for p in pos:
                sym   = p["symbol"]
                unreal = float(p["unrealizedPnl"])
                print(f"• {sym}: 미실현 PNL = ${unreal:.2f}")
    except Exception as e:
        print(f"❌ 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
