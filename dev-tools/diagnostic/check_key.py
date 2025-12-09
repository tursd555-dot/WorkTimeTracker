
import json

with open(r"C:\Temp\wtt_creds\service_account.json", "r", encoding="utf-8") as f:
    data = json.load(f)

pk = data["private_key"]

print("Тип ключа:", data.get("type"))
print("Email:", data.get("client_email"))
print("Начало ключа:", pk[:40])
print("Конец ключа:", pk[-40:])
print("Есть ли \\n внутри строки:", "\\n" in pk)