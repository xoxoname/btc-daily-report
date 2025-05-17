import os
import json
import requests

PREDICTION_FILE = "latest_prediction.json"

def save_prediction(data):
    try:
        with open(PREDICTION_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Prediction save failed: {e}")

def load_previous_prediction():
    try:
        if os.path.exists(PREDICTION_FILE):
            with open(PREDICTION_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Prediction load failed: {e}")
    return None

def get_bitget_data():
    try:
        response = requests.get("https://btc-daily-report.onrender.com/report")
        if response.status_code == 200:
            data = response.json()
            return {
                "realized": float(data.get("realized_pnl", 0)),
                "unrealized": float(data.get("unrealized_pnl", 0)),
                "margin": float(data.get("initial_margin", 1)),
                "positions": data.get("positions", [])
            }
    except Exception as e:
        print(f"Bitget fetch failed: {e}")
    return {
        "realized": 0,
        "unrealized": 0,
        "margin": 1,
        "positions": []
    }
