import urllib.request
import json
import time
import psycopg2

def send_update(payload):
    webhook_url = "http://localhost:5678/webhook/6203b22d-7f6e-4731-b245-0f6a913edfa1/webhook"
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=req_data,
        headers={
            "Content-Type": "application/json",
            "x-telegram-bot-api-secret-token": "zF67bIQS8ypAMElC_ca983051-1e1e-47a2-841b-a879fe4a7354"
        }
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read().decode("utf-8")

def get_latest_execution():
    conn = psycopg2.connect(
        dbname="tork_bot_db",
        user="tork_admin",
        password="tork_db_pass_2026",
        host="localhost",
        port=5432
    )
    cur = conn.cursor()
    cur.execute('SELECT id, status, mode, "startedAt", "stoppedAt" FROM execution_entity ORDER BY id DESC LIMIT 1;')
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_user_session(tg_user_id):
    conn = psycopg2.connect(
        dbname="tork_bot_db",
        user="tork_admin",
        password="tork_db_pass_2026",
        host="localhost",
        port=5432
    )
    cur = conn.cursor()
    cur.execute("SELECT tg_user_id, client_name, current_step, business_segment, updated_at FROM user_sessions_leads WHERE tg_user_id = %s;", (tg_user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def main():
    test_user_id = 5699064827

    print("=== TEST 1: Sending /start message ===")
    start_payload = {
        "update_id": int(time.time()),
        "message": {
            "message_id": int(time.time()) % 100000,
            "from": {
                "id": test_user_id,
                "is_bot": False,
                "first_name": "Erlan",
                "username": "erlan1502"
            },
            "chat": {
                "id": test_user_id,
                "first_name": "Erlan",
                "username": "erlan1502",
                "type": "private"
            },
            "date": int(time.time()),
            "text": "/start"
        }
    }
    status, body = send_update(start_payload)
    print(f"Webhook HTTP response: {status}, {body}")
    time.sleep(3)
    latest_exec = get_latest_execution()
    print(f"Latest Execution: {latest_exec}")
    session = get_user_session(test_user_id)
    print(f"Session in DB: {session}\n")

    print("=== TEST 2: Sending action_start_photo_fitting callback ===")
    callback_payload = {
        "update_id": int(time.time()) + 1,
        "callback_query": {
            "id": str(int(time.time())),
            "from": {
                "id": test_user_id,
                "is_bot": False,
                "first_name": "Erlan",
                "username": "erlan1502"
            },
            "message": {
                "message_id": int(time.time()) % 100000,
                "chat": {
                    "id": test_user_id,
                    "type": "private"
                },
                "date": int(time.time()),
                "text": "Welcome"
            },
            "data": "action_start_photo_fitting"
        }
    }
    status, body = send_update(callback_payload)
    print(f"Webhook HTTP response: {status}, {body}")
    time.sleep(3)
    latest_exec = get_latest_execution()
    print(f"Latest Execution: {latest_exec}")
    session = get_user_session(test_user_id)
    print(f"Session in DB: {session}")
    if session and session[2] == "AWAITING_PHOTO":
        print("SUCCESS: Session current_step is AWAITING_PHOTO!")
    else:
        print(f"WARNING: Session current_step is {session[2] if session else 'None'}")

if __name__ == "__main__":
    main()
