from flask import Flask, jsonify
from modules.report import format_profit_report_text, get_prediction_report

app = Flask(__name__)

@app.route("/report", methods=["GET"])
def report():
    try:
        profit_text = format_profit_report_text()
        prediction_text = get_prediction_report()

        return jsonify({
            "status": "success",
            "profit_report": profit_text,
            "prediction_report": prediction_text
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
