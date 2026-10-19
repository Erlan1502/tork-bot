import urllib.request
import json
import psycopg2

payload = {
    "event": "web_app_order",
    "company_name": "TOO ERLAN",
    "bin": "123456789012",
    "city": "Астана",
    "client_name": "Erlan Kubesov",
    "phone": "+7 (775) 930-38-21",
    "chat_id": 5699064827,
    "tg_user_id": 5699064827,
    "tg_username": "erlan1502",
    "items": [
        {
            "sku": "551000",
            "name": "Tork Matic® диспенсер полотенец в рулонах",
            "price": 131340,
            "qty": 1,
            "line_total": 131340,
            "system_code": "H1"
        }
    ],
    "total_amount": 131340
}

req_data = json.dumps(payload).encode('utf-8')
# Test via Nginx (port 8088) or direct n8n
webhook_url = "http://localhost:8088/webhook/web-app-order"

req = urllib.request.Request(
    webhook_url,
    data=req_data,
    headers={"Content-Type": "application/json"}
)

print(f"Sending test WebApp order to {webhook_url}...")
try:
    with urllib.request.urlopen(req) as resp:
        print("Webhook response code:", resp.status)
        print("Webhook response body:", resp.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)

# Check DB execution
conn = psycopg2.connect(
    dbname="tork_bot_db",
    user="tork_admin",
    password="tork_db_pass_2026",
    host="localhost",
    port=5432
)
cur = conn.cursor()
cur.execute("SELECT id, status, \"startedAt\", \"stoppedAt\" FROM execution_entity ORDER BY \"startedAt\" DESC LIMIT 1;")
row = cur.fetchone()
print("Latest execution:", row)
cur.close()
conn.close()
