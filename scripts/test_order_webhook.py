import urllib.request
import json
import time
import psycopg2

payload = {
    "update_id": int(time.time()),
    "message": {
        "message_id": int(time.time()) % 100000,
        "from": {
            "id": 5699064827,
            "is_bot": False,
            "first_name": "Erlan",
            "username": "erlan1502"
        },
        "chat": {
            "id": 5699064827,
            "first_name": "Erlan",
            "username": "erlan1502",
            "type": "private"
        },
        "date": int(time.time()),
        "web_app_data": {
            "data": json.dumps({
                "event": "web_app_order",
                "company_name": "ТОО Рассвет",
                "bin": "123456789012",
                "city": "Астана",
                "client_name": "Иван Иванов",
                "phone": "+7 (777) 123-45-67",
                "items": [
                    {
                        "sku": "551000",
                        "name": "Tork Matic® диспенсер полотенец в рулонах",
                        "price": 131340,
                        "qty": 2,
                        "line_total": 262680,
                        "system_code": "H1"
                    }
                ],
                "total_amount": 262680
            }),
            "button_text": "📄 Сформировать официальное КП"
        }
    }
}

req_data = json.dumps(payload).encode('utf-8')
webhook_url = "http://localhost:5678/webhook/6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook"

req = urllib.request.Request(
    webhook_url,
    data=req_data,
    headers={
        "Content-Type": "application/json",
        "x-telegram-bot-api-secret-token": "zF67bIQS8ypAMElC_ca983051-1e1e-47a2-841b-a879fe4a7354"
    }
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

# Wait a moment for execution
time.sleep(3)

# Check execution in DB
conn = psycopg2.connect(
    dbname='tork_bot_db',
    user='tork_admin',
    password='tork_db_pass_2026',
    host='localhost',
    port=5432
)
cur = conn.cursor()
cur.execute('SELECT id, status, mode, "startedAt", "stoppedAt" FROM execution_entity ORDER BY id DESC LIMIT 1;')
print("Latest execution:", cur.fetchone())

cur.execute("SELECT id, tg_user_id, tg_username, client_name, company_name, phone, distributor_id, current_step, selected_bundle, updated_at FROM user_sessions_leads WHERE tg_user_id = 5699064827;")
row = cur.fetchone()
print("\nUser session lead in DB after order:")
if row:
    print("ID:", row[0])
    print("tg_user_id:", row[1])
    print("tg_username:", row[2])
    print("client_name:", row[3])
    print("company_name:", row[4])
    print("phone:", row[5])
    print("distributor_id:", row[6])
    print("current_step:", row[7])
    print("selected_bundle:", json.dumps(row[8], indent=2, ensure_ascii=False) if row[8] else None)
    print("updated_at:", row[9])

cur.close()
conn.close()
