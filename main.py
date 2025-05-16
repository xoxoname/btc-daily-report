from flask import Flask
from modules.schedule import start_scheduler

app = Flask(__name__)

@app.route('/report', methods=['GET'])
def report():
    return "Report endpoint is active."

if __name__ == "__main__":
    start_scheduler()
    app.run(host='0.0.0.0', port=5000)
