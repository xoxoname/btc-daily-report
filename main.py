import os
import json
from flask import Flask, jsonify
from modules.report import (
    get_profit_report,
    format_profit_report_text,
    get_prediction_report,
    format_prediction_report_text
)

app = Flask(__name__)

@app.route('/')
def index():
    return 'BTC Report Service Running'

@app.route('/report')
def report():
    try:
        profit = get_profit_report()
        prediction = get_prediction_report()

        profit_text = format_profit_report_text(profit)
        prediction_text = format_prediction_report_text(prediction)

        response = {
            "profit_raw": profit,
            "prediction_raw": prediction,
            "profit_text": profit_text,
            "prediction_text": prediction_text
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
