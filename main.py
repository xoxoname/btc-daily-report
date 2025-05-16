from flask import Flask, request
from modules.schedule import start_scheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.utils import handle_profit_command, handle_prediction_command, handle_schedule_command

app = Flask(__name__)

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if str(chat_id) != TELEGRAM_CHAT_ID:
        return "Unauthorized", 403

    if "/수익" in text or "수익" in text:
        handle_profit_command(chat_id)
    elif "/예측" in text or "예측" in text:
        handle_prediction_command(chat_id)
    elif "/일정" in text or "일정" in text:
        handle_schedule_command(chat_id)

    return "ok", 200

@app.route("/report", methods=["GET"])
def report_status():
    from modules.report import build_report_text
    report = build_report_text()
    return {"message": report, "status": "success"}

if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=5000)
