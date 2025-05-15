import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv
from modules.report import get_prediction_report, format_profit_report_text

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/report", methods=["GET"])
def report_api():
    try:
        prediction = get_prediction_report()
        return jsonify({"report": prediction})
    except Exception as e:
        logger.error("/report API 실패", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

@app.route("/profit", methods=["GET"])
def profit_api():
    try:
        text = format_profit_report_text()
        return jsonify({"profit_report": text})
    except Exception as e:
        logger.error("/profit API 실패", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
