from flask import Flask
from report import get_profit_report, get_prediction_report, format_profit_report_text

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ BTC 리포트 서버가 실행 중입니다."

@app.route("/report")
def report_api():
    data = get_profit_report()
    return format_profit_report_text(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
