
import os, requests
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_BROADCAST_CHAT_ID")

assert TOKEN, "TELEGRAM_BOT_TOKEN не задан"
assert CHAT, "Ни TELEGRAM_ADMIN_CHAT_ID, ни TELEGRAM_BROADCAST_CHAT_ID не заданы"

resp = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT, "text": "✅ Тест из WorkTimeTracker", "disable_notification": False},
    timeout=10,
)
print("status:", resp.status_code)
print("resp:", resp.text)
resp.raise_for_status()
print("OK")