from flask import Flask, request
from modules.telegram import handle_command
from modules.utils import authorized

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
@authorized
def telegram_webhook():
    data = request.get_json()
    handle_command(data)
    return "ok", 200

if __name__ == '__main__':
    app.run(port=10000)