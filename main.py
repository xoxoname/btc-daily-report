# main.py

from flask import Flask
from modules.schedule import start_scheduler
from modules.emergency import start_emergency_monitor

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Report System is running."

if __name__ == "__main__":
    start_scheduler()
    start_emergency_monitor()
    app.run(host="0.0.0.0", port=10000)
