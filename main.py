import os
import ccxt
from datetime import datetime

# ┌───────────────────────────────────────────────────────────┐
# │                      환경 변수 세팅                       │
# └───────────────────────────────────────────────────────────┘
API_KEY       = os.environ['BITGET_API_KEY']
SECRET        = os.environ['BITGET_SECRET_KEY']
PASSPHRASE    = os.environ['BITGET_PASSPHRASE']
# (초기 자산 대비 등락률 계산용—처음 실행 시점의 자산을 저장해두세요)
INITIAL_EQUITY = float(os.environ.get('INITIAL_EQUITY', '0'))

# ┌───────────────────────────────────────────────────────────┐
# │                    CCXT 거래소 인스턴스                  │
# └───────────────────────────────────────────────────────────┘
exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET,
    'password': PASSPHRASE,
    'options': {'defaultType': 'swap'},
})

# ┌───────────────────────────────────────────────────────────┐
# │               보유 포지션(미실현 PNL) 조회                │
# └───────────────────────────────────────────────────────────┘
def fetch_open_positions():
    # ccxt 의 fetchPositions() 를 사용
    all_positions = exchange.fetchPositions()
    # contracts(수량)이 0 이 아닌 포지션만 리턴
    return [p for p in all_positions if float(p['contracts']) != 0]

# ┌───────────────────────────────────────────────────────────┐
# │                오늘 실현 PNL(가정: 0으로 대체)             │
# └───────────────────────────────────────────────────────────┘
def fetch_today_realized_pnl():
    # Bitget API 로 accountBill(endPoint) 등을 직접 호출해서 합산 가능
    # (편의상 여기서는 0.0 으로 리턴합니다)
    return 0.0

# ┌───────────────────────────────────────────────────────────┐
# │                   현재 자산(Equity) 조회                  │
# └───────────────────────────────────────────────────────────┘
def get_equity():
    bal = exchange.fetchBalance({'type': 'future'})
    # futures 계정의 USDT 총액 조회
    return float(bal['total']['USDT'])

# ┌───────────────────────────────────────────────────────────┐
# │                         메인 로직                        │
# └───────────────────────────────────────────────────────────┘
def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"✅ [BTC 실시간 리포트] {now}")
    print('----------------------------------------')

    # 1) 미실현 PNL 출력
    total_unrealized = 0.0
    for pos in fetch_open_positions():
        symbol         = pos['symbol']
        side           = pos['side']
        size           = float(pos['contracts'])
        entry_price    = float(pos['entryPrice'])
        unrealized_pnl = float(pos['info']['unrealisedPnl'])
        total_unrealized += unrealized_pnl
        # ★ 미실현 PNL 에 +/– 표시를 위해 +.4f 포맷 지정 ★
        print(f"📊 {symbol} | {side} | 수량: {size:.4f} | 진입가: {entry_price:.4f} | 미실현 PNL: {unrealized_pnl:+.4f} USDT")

    print(f"🧮 총 미실현 PNL: {total_unrealized:+.4f} USDT")

    # 2) 실현 PNL 출력
    today_realized = fetch_today_realized_pnl()
    print(f"💰 오늘 실현 PNL: {today_realized:+.4f} USDT")

    # 3) 자산 및 등락률 출력
    equity     = get_equity()
    if INITIAL_EQUITY > 0:
        change_pct = (equity - INITIAL_EQUITY) / INITIAL_EQUITY * 100
        print(f"💎 현재 자산: {equity:.2f} USDT ({change_pct:+.2f}%)")
    else:
        print(f"💎 현재 자산: {equity:.2f} USDT")

if __name__ == '__main__':
    main()
