from flask import Flask
from modules.emergency import check_btc_price_change

app = Flask(__name__)

@app.route("/")
def home():
    return "BTC Emergency Monitor Running"

# ✅ 앱 시작 시 테스트 메시지 1회 발송
check_btc_price_change()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
