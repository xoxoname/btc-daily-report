import time
from modules.telegram import start_bot

if __name__ == "__main__":
    print("📡 Starting Bitcoin Forecast Bot")
    while True:
        try:
            start_bot()
        except Exception as e:
            print(f"Fatal error: {e}")
        time.sleep(5)
