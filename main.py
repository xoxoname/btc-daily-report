import os
import json
from datetime import datetime, timedelta, timezone
import ccxt
from dotenv import load_dotenv

load_dotenv()  # Render에서는 무시됩니다. 환경변수로 설정하세요.

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

STATE_FILE = "balance_state.json"

def get_exchange():
    return ccxt.bitget({
        "apiKey": API_KEY,
        "secret": SECRET_KEY,
        "password": PASSPHRASE,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })

def load_state():
    if os.path.isfile(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"date": "", "start_balance": 0.0, "initial_balance": 0.0}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"))

def get_equity(exc):
    bal = exc.fetch_balance(params={"type": "future"})
    for acct in bal["info"]["data"]:
        if acct["marginCoin"] == "USDT":
            return float(acct["equity"])
    return float(bal["USDT"]["total"])

def get_unrealized(exc):
    total = 0.0
    for pos in exc.fetch_positions():
        c = float(pos.get("contracts", 0) or 0)
        if c > 0:
            total += float(pos.get("unrealizedPnl", 0))
    return total

def main():
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    today = now.strftime("%Y-%m-%d")

    exch = get_exchange()
    equity = get_equity(exch)
    unrealized = get_unrealized(exch)

    state = load_state()
    if state["initial_balance"] == 0.0:
        state["initial_balance"] = equity
    if state["date"] != today:
        state["date"] = today
        state["start_balance"] = equity

    delta = equity - state["start_balance"]
    realized = delta - unrealized
    cumulative = equity - state["initial_balance"]
    pct = (delta / state["start_balance"] * 100) if state["start_balance"] else 0.0

    save_state(state)

    print(f"[BTC 실시간 리포트] {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*40)
    print(f"💎 총 자산(Equity): {equity:.4f} USDT")
    print(f"🔺 수익률: {pct:+.2f}%")
    print(f"📊 오늘 실현 PnL: {realized:+.4f} USDT")
    print(f"📊 오늘 미실현 PnL: {unrealized:+.4f} USDT")
    print(f"💰 누적 PnL: {cumulative:+.4f} USDT")
    print("-"*40)

if __name__ == "__main__":
    main()
