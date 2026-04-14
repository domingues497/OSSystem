import os
import requests

class TelegramService:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.last_error = None

    def send(self, chat_id, message):
        self.last_error = None
        if not self.token or not chat_id or not message:
            self.last_error = "token/chat_id/message ausente"
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": str(chat_id), "text": message, "disable_web_page_preview": True}
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                return True
            self.last_error = f"HTTP {r.status_code}: {r.text[:300]}"
            return False
        except Exception as e:
            self.last_error = str(e)
            return False
