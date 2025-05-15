from flask import Flask, request
from modules.report import build_and_send_report
from modules.schedule import start_scheduler
from modules.emergency import start_emergency_monitor

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Daily Report is Running."

@app.route("/report", methods=["GET"])
def trigger_report():
    try:
        build_and_send_report()
        return "Report triggered successfully.", 200
    except Exception as e:
        return f"Error triggering report: {e}", 500

if __name__ == "__main__":
    start_scheduler()
    start_emergency_monitor()
    app.run(host="0.0.0.0", port=10000)
