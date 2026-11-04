#!/usr/bin/env python3
"""
Phase 3 Workflow Updater
Updates workflows/tork_bot_workflow.json and PostgreSQL n8n database:
1. Updates 'Send Manager Result Photo' inline keyboard with:
   - [ 📊 Скачать презентацию (PDF) ] (callback_data: download_presentation)
   - [ 🔄 Выбрать другой диспенсер ] (callback_data: change_dispenser)
2. Adds 'Handle Change Dispenser' HTTP node (calling POST /api/manager/change-dispenser)
3. Adds 'Handle Restore Montage' HTTP node (calling POST /api/manager/restore-montage)
4. Updates 'Route by Event Type' Switch node to route:
   - branch 0 (web_app_select) -> Parse Selected Dispenser
   - branch 1 (photo) -> Download Telegram Photo
   - branch 2 (download_presentation) -> Render & Send Presentation
   - branch 3 (change_dispenser) -> Handle Change Dispenser
   - branch 4 (restore_previous_montage) -> Handle Restore Montage
   - branch 5 (callback) -> Send Manager Welcome & Menu
   - fallback (text_or_other) -> Send Manager Welcome & Menu
"""

import json
import os
import sys
from pathlib import Path
import psycopg2

ROOT = Path(__file__).resolve().parent.parent

def update_workflow():
    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_array = isinstance(data, list)
    wf = data[0] if is_array else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    connections = wf.get("connections", {})

    # 1. Update Send Manager Result Photo with correct Phase 3 inline keyboard
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
                                "text": "🔄 Выбрать другой диспенсер",
                                "additionalFields": {
                                    "callback_data": "change_dispenser"
                                }
                            }
                        ]
                    }
                }
            ]
        }

    # 2. Add Handle Change Dispenser Node
    change_dispenser_node = {
        "parameters": {
            "method": "POST",
            "url": "http://dashboard_api:8000/api/manager/change-dispenser",
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
        "id": "node-handle-change-dispenser",
        "name": "Handle Change Dispenser",
        "type": "n8n-nodes-base.httpRequest",
        "position": [0, 680],
        "typeVersion": 4.2
    }
    nodes["Handle Change Dispenser"] = change_dispenser_node

    # 3. Add Handle Restore Montage Node
    restore_montage_node = {
        "parameters": {
            "method": "POST",
            "url": "http://dashboard_api:8000/api/manager/restore-montage",
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
        "id": "node-handle-restore-montage",
        "name": "Handle Restore Montage",
        "type": "n8n-nodes-base.httpRequest",
        "position": [220, 680],
        "typeVersion": 4.2
    }
    nodes["Handle Restore Montage"] = restore_montage_node

    # 4. Route by Event Type (Switch node) configuration
    cond_expr = (
        "={{ "
        "($json.callback_query?.data === 'download_presentation' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'download_presentation' || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/pdf') || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/presentation')) ? 'download_presentation' : "
        "(($json.callback_query?.data === 'change_dispenser' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'change_dispenser' || $json.callback_query?.data === 'select_other_dispenser' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'select_other_dispenser') ? 'change_dispenser' : "
        "(($json.callback_query?.data === 'restore_previous_montage' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'restore_previous_montage' || $json.callback_query?.data === 'undo_dispenser_change' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'undo_dispenser_change') ? 'restore_previous_montage' : "
        "(($json.message?.web_app_data?.data || $('Telegram Trigger').first()?.json?.message?.web_app_data?.data || $('Telegram Trigger').item?.json?.message?.web_app_data?.data) ? 'web_app_select' : "
        "(((($json.message?.photo || $('Telegram Trigger').first()?.json?.message?.photo) || (($json.message?.document || $('Telegram Trigger').first()?.json?.message?.document) && (($json.message?.document?.mime_type || $('Telegram Trigger').first()?.json?.message?.document?.mime_type) || '').startsWith('image/')))) ? 'photo' : "
        "(($json.callback_query || $('Telegram Trigger').first()?.json?.callback_query || $('Telegram Trigger').item?.json?.callback_query) ? 'callback' : 'other'))))) "
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
            },
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "operator": {"operation": "equals", "type": "string"},
                            "rightValue": "change_dispenser",
                            "id": "rule-change-dispenser",
                            "leftValue": cond_expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "change_dispenser"
            },
            {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "operator": {"operation": "equals", "type": "string"},
                            "rightValue": "restore_previous_montage",
                            "id": "rule-restore-montage",
                            "leftValue": cond_expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "restore_previous_montage"
            }
        ]
        route_node["parameters"]["options"] = {
            "fallbackOutput": "extra",
            "renameFallbackOutput": "text_or_other"
        }

    # 5. Wire Connections
    # Route by Event Type outputs:
    # 0 -> Parse Selected Dispenser
    # 1 -> Download Telegram Photo
    # 2 -> Render & Send Presentation
    # 3 -> Send Manager Welcome & Menu (callback)
    # 4 -> Handle Change Dispenser
    # 5 -> Handle Restore Montage
    # Fallback (index 6) -> Send Manager Welcome & Menu (text_or_other)
    connections["Route by Event Type"] = {
        "main": [
            [{"node": "Parse Selected Dispenser", "type": "main", "index": 0}],
            [{"node": "Download Telegram Photo", "type": "main", "index": 0}],
            [{"node": "Render & Send Presentation", "type": "main", "index": 0}],
            [{"node": "Send Manager Welcome & Menu", "type": "main", "index": 0}],
            [{"node": "Handle Change Dispenser", "type": "main", "index": 0}],
            [{"node": "Handle Restore Montage", "type": "main", "index": 0}],
            [{"node": "Send Manager Welcome & Menu", "type": "main", "index": 0}]
        ]
    }

    node_list = list(nodes.values())
    wf["nodes"] = node_list
    wf["connections"] = connections

    new_data = [wf] if is_array else wf
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"Updated {workflow_path} successfully. Total nodes: {len(node_list)}")

    # Update PostgreSQL n8n tables if reachable
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
