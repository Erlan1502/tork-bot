import os
import json
import urllib.request
from pathlib import Path

def load_env(env_path):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip("'\"")
    return env_vars

def main():
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    env_vars = load_env(env_path)

    token = os.getenv("TELEGRAM_BOT_TOKEN") or env_vars.get("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL") or env_vars.get("WEBHOOK_URL", "https://romaine-towery-audrey.ngrok-free.dev")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment or .env")

    webapp_url = f"{webhook_url.rstrip('/')}/app/index.html"
    api_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"

    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "📝 Создать заказ",
            "web_app": {
                "url": webapp_url
            }
        }
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"Success! Response: {resp_body}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        raise
    except Exception as e:
        print(f"Error setting chat menu button: {e}")
        raise

if __name__ == "__main__":
    main()
