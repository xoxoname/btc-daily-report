from flask import Flask, jsonify
from modules.report import get_prediction_report, format_profit_report_text
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ BTC 데일리 리포트 서버 정상 작동 중입니다."

@app.route("/report", methods=["GET"])
def report_api():
    try:
        prediction = get_prediction_report()

        # 예시용 PnL 데이터 (Bitget API와 연동 시 실제 값으로 대체)
        pnl_data = {
            "realized_pnl": 153.2,
            "unrealized_pnl": 78.5
        }

        profit_report = format_profit_report_text(pnl_data)

        return jsonify({
            "message": "success",
            "prediction": prediction,
            "profit_report": profit_report
        })

    except Exception as e:
        print(f"/report API 실패: {e}")
        return jsonify({
            "message": str(e),
            "status": "error"
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
