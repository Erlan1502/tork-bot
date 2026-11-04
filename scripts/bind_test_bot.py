import os
import urllib.request
import json
import re

def get_env_var(key, default=""):
    val = os.getenv(key)
    if not val and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    val = line.split("=", 1)[1].strip()
                    break
    return val or default

BOT_TOKEN = get_env_var("TELEGRAM_BOT_TOKEN")
TUNNEL_URL = get_env_var("WEBHOOK_URL", "https://bids-infections-possession-first.trycloudflare.com")
WEBHOOK_PATH = "/webhook/6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook"
SECRET_TOKEN = "sHnoGT842oAJacFu_ca983051-1e1e-47a2-841b-a879fe4a7354"

full_webhook_url = f"{TUNNEL_URL}{WEBHOOK_PATH}"

print(f"Binding bot to webhook: {full_webhook_url}")

# 1. Set Webhook
payload = {
    "url": full_webhook_url,
    "allowed_updates": ["message", "callback_query"]
}
req = urllib.request.Request(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode())
    print("setWebhook result:", res)

# 2. Check Webhook Info
with urllib.request.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo") as resp:
    info = json.loads(resp.read().decode())
    print("getWebhookInfo result:", json.dumps(info, indent=2))

# 3. Set Menu Button
menu_payload = {
    "menu_button": {
        "type": "web_app",
        "text": "✨ Каталог Tork",
        "web_app": {
            "url": f"{TUNNEL_URL}/app/index.html"
        }
    }
}
menu_req = urllib.request.Request(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMenuButton",
    data=json.dumps(menu_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(menu_req) as resp:
    res = json.loads(resp.read().decode())
    print("setChatMenuButton result:", res)

