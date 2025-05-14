import os
import json
from datetime import datetime, timedelta, timezone
import ccxt
from dotenv import load_dotenv

# ❶ .env 파일은 로컬 개발 시에만 사용하고,
#     Render 에서는 대시보드 환경변수로 API 키를 설정하세요.
load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

# ❷ 파일에 오늘자 시작잔고와 최초잔고를 저장할 경로
STATE_FILE = "balance_state.json"

def get_exchange():
    return ccxt.bitget({
        "apiKey": API_KEY,
        "secret": SECRET_KEY,
        "password": PASSPHRASE,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},  # USDT perpetual futures
    })

def load_state():
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    # 초기값 설정
    return {
        "date": "",
        "start_balance": 0.0,
        "initial_balance": 0.0,
    }

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_equity(exchange):
    # futures account 정보에서 equity(순자산) 조회
    bal = exchange.fetch_balance(params={"type": "future"})
    # ccxt 비트겟은 bal['info']['data'] 리스트 안에 각 마진코인별 equity를 줌
    for acct in bal["info"]["data"]:
        if acct["marginCoin"] == "USDT":
            return float(acct["equity"])
    # fallback: unified balance
    return float(bal["USDT"]["total"])

def get_unrealized(exchange):
    # 열린 포지션들의 unrealized PnL 합산
    positions = exchange.fetch_positions()
    total = 0.0
    for pos in positions:
        # 포지션이 열려있어야만 계산
        if pos["contracts"] and float(pos["contracts"]) > 0:
            total += float(pos.get("unrealizedPnl", 0))
    return total

def main():
    # 0시 기준 오늘 날짜 문자열
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    today = now.strftime("%Y-%m-%d")

    exch = get_exchange()
    equity = get_equity(exch)
    unrealized = get_unrealized(exch)

    # 상태 불러오기
    state = load_state()

    # 최초 실행 시 initial_balance 설정
    if state["initial_balance"] == 0.0:
        state["initial_balance"] = equity

    # 날짜가 바뀌었다면, start_balance 업데이트
    if state["date"] != today:
        state["date"] = today
        state["start_balance"] = equity

    # 오늘 실현 PnL은 (전체 변화량 − 미실현 PnL)
    delta_total = equity - state["start_balance"]
    realized = delta_total - unrealized

    # 누적 PnL은 (현 재산 − 최초잔고)
    cumulative = equity - state["initial_balance"]

    # 수익률
    pct_change = 0.0
    if state["start_balance"] > 0:
        pct_change = (delta_total / state["start_balance"]) * 100

    # 상태 저장
    save_state(state)

    # 출력
    header = f"[BTC 실시간 리포트] {now.strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"{header}\n" + "-"*40)
    print(f"💎 총 자산(Equity): {equity:.4f} USDT")
    print(f"🔺 수익률: {pct_change:+.2f}%")
    print(f"📊 오늘 실현 PnL: {realized:+.4f} USDT")
    print(f"📊 오늘 미실현 PnL: {unrealized:+.4f} USDT")
    print(f"💰 누적 PnL: {cumulative:+.4f} USDT")
    print("-"*40)

if __name__ == "__main__":
    main()
