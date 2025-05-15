from flask import Flask, jsonify
from modules.report import get_prediction_report, format_profit_report_text

app = Flask(__name__)

@app.route('/report')
def report():
    prediction = get_prediction_report()
    profit_report = format_profit_report_text()
    return jsonify({
        "prediction": prediction,
        "profit_report": profit_report
    })

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0", port=10000)
