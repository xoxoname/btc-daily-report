# main.py
import os
import time
from datetime import datetime, timezone, timedelta
import ccxt

def main():
    # 1) 환경변수에서 키·시크릿 읽어서 CCXT Bitget 인스턴스 생성
    api_key    = os.getenv("BITGET_API_KEY")
    secret     = os.getenv("BITGET_SECRET_KEY")
    passphrase = os.getenv("BITGET_PASSPHRASE")
    if not (api_key and secret and passphrase):
        print("❌ 환경변수 BITGET_API_KEY/SECRET_KEY/PASSPHRASE 중 하나가 설정되지 않았습니다.")
        return

    exchange = ccxt.bitget({
        "apiKey": api_key,
        "secret": secret,
        "password": passphrase,
        "enableRateLimit": True,
    })
    # USDT-M 선물(Perpetual) 마켓으로 설정
    exchange.options["defaultType"] = "future"

    # 2) 타임스탬프 찍기 (한국시간)
    now = datetime.now(timezone(timedelta(hours=9)))
    header = f"\n✅ [BTC 실시간 리포트] {now.strftime('%Y-%m-%d %H:%M:%S')}\n" + "-"*40
    print(header)

    # 3) 오늘 PNL은 CCXT가 직접 제공하진 않지만,
    #    balance.fetchBalance 후 position들 합산해서 대략 이틀치 변화로 뽑아볼 수 있습니다.
    #    여기서는 간단히 미실현 PNL만 보여드릴게요.

    try:
        positions = exchange.fetch_positions()  # 모든 선물 포지션
        unrealized_total = 0.0
        for pos in positions:
            # contracts(계약 수)가 0 초과인 포지션만
            if pos.get("contracts", 0) > 0:
                upnl = pos.get("unrealizedPnl", 0.0) or pos.get("unrealized_profit", 0.0)
                symbol = pos.get("symbol")
                side   = pos.get("side")
                amt    = pos.get("contracts")
                entry  = pos.get("entryPrice") or pos.get("entry_price")
                print(f"📊 {symbol:<8} | {side:>4} | 수량: {amt:.4f} | 진입가: {entry:.1f} | 미실현 PNL: {upnl:.4f} USDT")
                unrealized_total += float(upnl)
        if unrealized_total == 0:
            print("📭 현재 열린 포지션이 없거나, 미실현 PNL이 없습니다.")
        else:
            print(f"🧮 총 미실현 PNL: {unrealized_total:.4f} USDT")
    except Exception as e:
        print(f"❌ 실시간 포지션 조회 실패: {e}")

if __name__ == "__main__":
    main()
