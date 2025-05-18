import requests

class TelegramBot:
    def __init__(self, token, chat_id):
        self.base_url = f'https://api.telegram.org/bot{token}'
        self.chat_id = chat_id

    def send_report(self, content):
        requests.post(
            f'{self.base_url}/sendMessage',
            json={'chat_id': self.chat_id, 'text': content, 'parse_mode': 'Markdown'}
        )

    def send_alert(self, message):
        requests.post(
            f'{self.base_url}/sendMessage',
            json={'chat_id': self.chat_id, 'text': f'🚨 {message}'}
        )
