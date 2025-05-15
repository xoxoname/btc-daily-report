# main.py
from flask import Flask, jsonify
from modules.schedule import sched  # 스케줄러 자동 시작
from modules.report import build_and_send_report

app = Flask(__name__)

@app.route("/report", methods=["GET"])
def report():
    try:
        text = build_and_send_report()
        return jsonify({"status":"ok","report":text})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
