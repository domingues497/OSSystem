import os
import requests

class TelegramService:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")

    def send(self, chat_id, message):
        if not self.token or not chat_id or not message:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": str(chat_id), "text": message, "disable_web_page_preview": True}
            r = requests.post(url, json=payload, timeout=10)
            return r.status_code == 200
        except Exception:
            return False
