from flask import Flask, request
from modules.report import get_prediction_report, format_profit_report_text

app = Flask(__name__)

@app.route("/report")
def report():
    prediction = get_prediction_report()
    return prediction

@app.route("/profit")
def profit():
    return format_profit_report_text()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
