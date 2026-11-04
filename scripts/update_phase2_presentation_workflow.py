import json
import os
import sys
import psycopg2

def update_workflow():
    workflow_path = "workflows/tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_array = isinstance(data, list)
    wf = data[0] if is_array else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    connections = wf.get("connections", {})

    webapp_url_expr = "={{ ($env.WEBHOOK_URL ? $env.WEBHOOK_URL.replace(/\\/+$/, '') : 'http://localhost:8088') + '/app/index.html' }}"

    # 1. Update Send Manager Result Photo with [📊 Скачать презентацию (PDF)] button
    if "Send Manager Result Photo" in nodes:
        nodes["Send Manager Result Photo"]["parameters"]["replyMarkup"] = "inlineKeyboard"
        nodes["Send Manager Result Photo"]["parameters"]["inlineKeyboard"] = {
            "rows": [
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "📊 Скачать презентацию (PDF)",
                                "additionalFields": {
                                    "callback_data": "download_presentation"
                                }
                            }
                        ]
                    }
                },
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "🔄 Примерить другой диспенсер",
                                "additionalFields": {
                                    "web_app": {
                                        "url": webapp_url_expr
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }

    # 2. Add New Node: Render & Send Presentation (HTTP Request)
    render_pres_node = {
        "parameters": {
            "method": "POST",
            "url": "http://dashboard_api:8000/api/manager/render-presentation",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Content-Type",
                        "value": "application/json"
                    }
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({\n"
                "  telegram_id: $('Telegram Trigger').first()?.json?.callback_query ? $('Telegram Trigger').first().json.callback_query.from.id : ($('Telegram Trigger').first()?.json?.message ? $('Telegram Trigger').first().json.message.from.id : ($json.from ? $json.from.id : 0)),\n"
                "  chat_id: $('Telegram Trigger').first()?.json?.callback_query ? ($('Telegram Trigger').first().json.callback_query.message ? $('Telegram Trigger').first().json.callback_query.message.chat.id : $('Telegram Trigger').first().json.callback_query.from.id) : ($('Telegram Trigger').first()?.json?.message ? $('Telegram Trigger').first().json.message.chat.id : ($json.chat ? $json.chat.id : 0)),\n"
                "  callback_query_id: $('Telegram Trigger').first()?.json?.callback_query ? $('Telegram Trigger').first().json.callback_query.id : undefined,\n"
                "  send_to_telegram: true\n"
                "}) }}"
            ),
            "options": {}
        },
        "id": "node-render-presentation",
        "name": "Render & Send Presentation",
        "type": "n8n-nodes-base.httpRequest",
        "position": [0, 520],
        "typeVersion": 4.2
    }
    nodes["Render & Send Presentation"] = render_pres_node

    # 3. Update Route by Event Type (Switch node) to support download_presentation
    cond_expr = (
        "={{ "
        "($json.callback_query?.data === 'download_presentation' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'download_presentation' || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/pdf') || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/presentation')) ? 'download_presentation' : "
        "(($json.message?.web_app_data?.data || $('Telegram Trigger').first()?.json?.message?.web_app_data?.data || $('Telegram Trigger').item?.json?.message?.web_app_data?.data) ? 'web_app_select' : "
        "(((($json.message?.photo || $('Telegram Trigger').first()?.json?.message?.photo) || (($json.message?.document || $('Telegram Trigger').first()?.json?.message?.document) && (($json.message?.document?.mime_type || $('Telegram Trigger').first()?.json?.message?.document?.mime_type) || '').startsWith('image/')))) ? 'photo' : "
        "(($json.callback_query || $('Telegram Trigger').first()?.json?.callback_query || $('Telegram Trigger').item?.json?.callback_query) ? 'callback' : 'other'))) "
        "}}"
    )

    if "Route by Event Type" in nodes:
        route_node = nodes["Route by Event Type"]
        route_node["parameters"]["rules"]["values"] = [
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "operator": {"operation": "equals", "type": "string"},
                            "rightValue": "web_app_select",
                            "id": "rule-web-app-select",
                            "leftValue": cond_expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "web_app_select"
            },
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "operator": {"operation": "equals", "type": "string"},
                            "rightValue": "photo",
                            "id": "rule-photo",
                            "leftValue": cond_expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "photo"
            },
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "operator": {"operation": "equals", "type": "string"},
                            "rightValue": "download_presentation",
                            "id": "rule-download-pres",
                            "leftValue": cond_expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "download_presentation"
            },
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "operator": {"operation": "equals", "type": "string"},
                            "rightValue": "callback",
                            "id": "rule-callback",
                            "leftValue": cond_expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "callback"
            }
        ]
        route_node["parameters"]["options"] = {
            "fallbackOutput": "extra",
            "renameFallbackOutput": "text_or_other"
        }

    # 4. Wire Connections
    # Route by Event Type:
    # Output 0 (web_app_select) -> Parse Selected Dispenser
    # Output 1 (photo) -> Download Telegram Photo
    # Output 2 (download_presentation) -> Render & Send Presentation
    # Output 3 (callback) -> Send Manager Welcome & Menu
    # Fallback (text_or_other) -> Send Manager Welcome & Menu
    connections["Route by Event Type"] = {
        "main": [
            [{"node": "Parse Selected Dispenser", "type": "main", "index": 0}],
            [{"node": "Download Telegram Photo", "type": "main", "index": 0}],
            [{"node": "Render & Send Presentation", "type": "main", "index": 0}],
            [{"node": "Send Manager Welcome & Menu", "type": "main", "index": 0}],
            [{"node": "Send Manager Welcome & Menu", "type": "main", "index": 0}]
        ]
    }

    node_list = list(nodes.values())
    wf["nodes"] = node_list
    wf["connections"] = connections

    # Write back to JSON file
    new_data = [wf] if is_array else wf
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"Updated {workflow_path} successfully. Total nodes: {len(node_list)}")

    # Update PostgreSQL n8n tables
    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = int(os.getenv("POSTGRES_PORT", "5433"))
    pg_user = os.getenv("POSTGRES_USER", "tork_admin")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "supersecret_tork_kz_pass")
    pg_db = os.getenv("POSTGRES_DB", "tork_bot_db")

    try:
        conn = psycopg2.connect(
            dbname=pg_db,
            user=pg_user,
            password=pg_pass,
            host=pg_host,
            port=pg_port
        )
        cur = conn.cursor()

        # Update all active workflow entities
        cur.execute(
            """
            UPDATE workflow_entity 
            SET nodes = %s, connections = %s, "updatedAt" = NOW() 
            WHERE active = true;
            """,
            (json.dumps(node_list), json.dumps(connections))
        )
        updated_count = cur.rowcount

        cur.execute(
            """
            UPDATE workflow_history 
            SET nodes = %s, connections = %s, "updatedAt" = NOW() 
            WHERE "workflowId" IN (SELECT id FROM workflow_entity WHERE active = true);
            """,
            (json.dumps(node_list), json.dumps(connections))
        )

        conn.commit()
        cur.close()
        conn.close()
        print(f"Updated {updated_count} active workflow_entity rows in PostgreSQL successfully.")
    except Exception as e:
        print(f"Warning: Could not update workflow in DB directly: {e}")

if __name__ == "__main__":
    update_workflow()
