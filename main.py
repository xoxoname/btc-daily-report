import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv
from modules.report import get_prediction_report, format_profit_report_text

# .env 로드 (OPENAI_API_KEY, PORT 등)
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask 앱 초기화
app = Flask(__name__)

@app.route("/report", methods=["GET"])
def report_api():
    """비트코인 예측 리포트를 반환합니다."""
    try:
        prediction = get_prediction_report()
        return jsonify({"report": prediction})
    except Exception as e:
        logger.error("/report API 실패", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

@app.route("/profit", methods=["GET"])
def profit_api():
    """실현/미실현 손익 리포트를 반환합니다."""
    try:
        text = format_profit_report_text()
        return jsonify({"profit_report": text})
    except Exception as e:
        logger.error("/profit API 실패", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

if __name__ == "__main__":
    # Render 또는 환경변수에서 PORT 가져오기 (없으면 5000)
    port = int(os.getenv("PORT", 5000))
    # 모든 인터페이스에서 리스닝
    app.run(host="0.0.0.0", port=port)
