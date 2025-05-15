from flask import Flask, jsonify
from modules.report import build_and_send_report

app = Flask(__name__)

@app.route("/report")
def report():
    try:
        result = build_and_send_report()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "status": "failed"})

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
