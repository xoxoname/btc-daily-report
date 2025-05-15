def check_btc_price_change():
    try:
        response = requests.get("https://api.coindesk.com/v1/bpi/currentprice/BTC.json", timeout=5)
        data = response.json()
        price_usd = float(data["bpi"]["USD"]["rate"].replace(",", ""))

        # ✅ 테스트용: 강제로 이전 가격과 차이를 3%로 만들어서 푸시 발생
        check_btc_price_change.last_price = price_usd * 1.03

        delta = abs(price_usd - check_btc_price_change.last_price) / check_btc_price_change.last_price
        if delta >= 0.02:
            msg = f"""📛 *BTC 긴급 변동 감지!*
💰 현재 BTC 가격: ${price_usd:,.2f}
📉 변화율: {delta*100:.2f}%"""
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                params={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            )
        check_btc_price_change.last_price = price_usd

    except Exception as e:
        print(f"[긴급 감지 오류]: {e}")
