import json
import psycopg2
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent.parent
    workflow_path = root_dir / "workflows" / "tork_bot_workflow.json"

    with open(workflow_path, "r", encoding="utf-8") as f:
        workflows_data = json.load(f)

    wf = workflows_data[0] if isinstance(workflows_data, list) else workflows_data
    nodes = wf["nodes"]
    connections = wf["connections"]

    # 1. Update Send Segment Keyboard -> Send Welcome Onboarding
    welcome_text = (
        "👋 Добро пожаловать в Tork AI Казахстан!\n\n"
        "Официальный сервис подбора профессионального гигиенического оборудования "
        "и расходных материалов Tork (Essity).\n\n"
        "Выберите удобный способ работы:\n"
        "• Откройте интерактивный каталог, чтобы самостоятельно собрать спецификацию "
        "и получить официальное КП с ценами в KZT.\n"
        "• Или воспользуйтесь AI-примеркой диспенсеров по фотографии вашего санузла."
    )

    welcome_keyboard = {
        "rows": [
            {
                "row": {
                    "buttons": [
                        {
                            "text": "📝 Открыть каталог Tork",
                            "additionalFields": {
                                "web_app": {
                                    "url": "https://romaine-towery-audrey.ngrok-free.dev/app/index.html"
                                }
                            }
                        }
                    ]
                }
            },
            {
                "row": {
                    "buttons": [
                        {
                            "text": "📸 Подобрать по фото санузла",
                            "additionalFields": {
                                "callback_data": "action_start_photo_fitting"
                            }
                        }
                    ]
                }
            }
        ]
    }

    send_welcome_node = next((n for n in nodes if n["name"] in ["Send Segment Keyboard", "Send Welcome Onboarding"]), None)
    if send_welcome_node:
        send_welcome_node["name"] = "Send Welcome Onboarding"
        send_welcome_node["parameters"]["text"] = welcome_text
        send_welcome_node["parameters"]["replyMarkup"] = "inlineKeyboard"
        send_welcome_node["parameters"]["inlineKeyboard"] = welcome_keyboard
        send_welcome_node["parameters"]["additionalFields"] = {
            "appendAttribution": False
        }
        print("Updated Send Welcome Onboarding node.")

    # 2. Update Route by Event Type connections
    if "Route by Event Type" in connections:
        main_conns = connections["Route by Event Type"].get("main", [])
        if len(main_conns) > 3:
            main_conns[3] = [
                {
                    "node": "Send Welcome Onboarding",
                    "type": "main",
                    "index": 0
                }
            ]
            print("Updated Route by Event Type fallback connection -> Send Welcome Onboarding.")

    if "Send Segment Keyboard" in connections:
        del connections["Send Segment Keyboard"]

    # 3. Update Send Photo Request
    photo_request_text = (
        "📷 Пожалуйста, отправьте фотографию стены и зоны раковины санузла "
        "(с расстояния 1.5–2 метра). Нейросеть проанализирует интерьер "
        "и примерит подходящий диспенсер Tork."
    )
    send_photo_req_node = next((n for n in nodes if n["name"] == "Send Photo Request"), None)
    if send_photo_req_node:
        send_photo_req_node["parameters"]["text"] = photo_request_text
        send_photo_req_node["parameters"]["additionalFields"] = {
            "appendAttribution": False
        }
        print("Updated Send Photo Request node.")

    # 4. Update Update Session Segment (callback handler SQL)
    update_session_node = next((n for n in nodes if n["name"] == "Update Session Segment"), None)
    if update_session_node:
        update_session_node["parameters"]["query"] = (
            "UPDATE user_sessions_leads "
            "SET current_step = 'AWAITING_PHOTO', "
            "business_segment = COALESCE(NULLIF(regexp_replace('{{ $('Telegram Trigger').item.json.callback_query.data || '' }}', '^seg_', ''), 'action_start_photo_fitting'), business_segment, 'HoReCa'), "
            "updated_at = NOW() "
            "WHERE tg_user_id = {{ $('Telegram Trigger').item.json.callback_query.from.id }} "
            "RETURNING *;"
        )
        print("Updated Update Session Segment SQL query.")

    # 5. Update Send Client Result & Inline Buttons
    send_result_node = next((n for n in nodes if n["name"] == "Send Client Result & Inline Buttons"), None)
    if send_result_node:
        send_result_node["parameters"]["replyMarkup"] = "inlineKeyboard"
        send_result_node["parameters"]["inlineKeyboard"] = {
            "rows": [
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "🛒 Оформить комплект в каталоге",
                                "additionalFields": {
                                    "web_app": {
                                        "url": "=https://romaine-towery-audrey.ngrok-free.dev/app/index.html?preselect_sku={{ $json.dispenser_sku }}"
                                    }
                                }
                            }
                        ]
                    }
                },
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "🔄 Примерить другой цвет",
                                "additionalFields": {
                                    "callback_data": "action_change_color"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        send_result_node["parameters"]["additionalFields"] = {
            "appendAttribution": False
        }
        print("Updated Send Client Result & Inline Buttons node.")

    wf["nodes"] = nodes
    wf["connections"] = connections

    # Save workflow file
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump([wf] if isinstance(workflows_data, list) else wf, f, indent=2, ensure_ascii=False)
    print(f"Saved updated workflow to {workflow_path}")

    # Update Database
    conn = psycopg2.connect(
        dbname="tork_bot_db",
        user="tork_admin",
        password="tork_db_pass_2026",
        host="localhost",
        port=5432
    )
    cur = conn.cursor()

    # Find active workflow ID
    cur.execute("SELECT id FROM workflow_entity WHERE active = true;")
    rows = cur.fetchall()
    wf_ids = [r[0] for r in rows] if rows else ['zF67bIQS8ypAMElC']
    print(f"Active workflow IDs in DB: {wf_ids}")

    for w_id in wf_ids:
        cur.execute("""
            UPDATE workflow_entity 
            SET nodes = %s, connections = %s, active = true, "updatedAt" = NOW() 
            WHERE id = %s;
        """, (json.dumps(nodes), json.dumps(connections), w_id))

        cur.execute("""
            UPDATE workflow_history 
            SET nodes = %s, connections = %s, "updatedAt" = NOW() 
            WHERE "workflowId" = %s;
        """, (json.dumps(nodes), json.dumps(connections), w_id))
        print(f"Updated workflow {w_id} in DB.")

    conn.commit()
    cur.close()
    conn.close()
    print("Database updated successfully.")

if __name__ == "__main__":
    main()
