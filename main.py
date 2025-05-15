from flask import Flask, jsonify
from modules.report import get_prediction_report, format_profit_report_text

app = Flask(__name__)

@app.route("/")
def health_check():
    return "✅ BTC Report Service is running!"

@app.route("/report")
def report_api():
    try:
        prediction = get_prediction_report()

        # 예시용 수익 데이터 (실제 Bitget API로 대체 가능)
        profit_data = {
            "realized_pnl": 124.5,
            "unrealized_pnl": -32.1,
            "total_assets": 5423.88,
            "roi": 6.42,
            "timestamp": "2025-05-15 14:30"
        }
        profit_text = format_profit_report_text(profit_data)

        return jsonify({
            "status": "success",
            "prediction": prediction,
            "profit_report": profit_text
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
