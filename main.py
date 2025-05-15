import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv

from modules.report import build_and_send_report
from modules.profit import get_profit_data

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/report", methods=["GET"])
def report_api():
    try:
        content = build_and_send_report()
        return jsonify({"report": content})
    except Exception as e:
        logger.error("Report API 실패", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

@app.route("/profit", methods=["GET"])
def profit_api():
    try:
        data = get_profit_data()
        return jsonify(data)
    except Exception as e:
        logger.error("Profit API 실패", exc_info=e)
        return jsonify({"message": str(e), "status": "error"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
