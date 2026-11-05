#!/usr/bin/env python3
"""
Phase 4 Workflow Updater for Commercial Proposal (KP Kazakhstan):
1. Updates 'Send Manager Result Photo' inline keyboard with:
   - [ 📄 Создать КП (5 стр. PDF) ] (callback_data: create_kp)
   - [ 📊 Скачать презентацию (PDF) ] (callback_data: download_presentation)
   - [ 🔄 Выбрать другой диспенсер ] (callback_data: change_dispenser)
2. Adds 'Render & Send Commercial Proposal' HTTP node calling POST http://dashboard_api:8000/api/manager/generate-kp
3. Updates 'Route by Event Type' Switch node to add 'create_kp' routing branch.
4. Syncs the workflow to n8n database and workflows/tork_bot_workflow.json.
"""

import json
import os
import sys
from pathlib import Path
import psycopg2

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

def update_workflow():
    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_array = isinstance(data, list)
    wf = data[0] if is_array else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    connections = wf.get("connections", {})

    # 1. Update Send Manager Result Photo inline keyboard
    if "Send Manager Result Photo" in nodes:
        nodes["Send Manager Result Photo"]["parameters"]["replyMarkup"] = "inlineKeyboard"
        nodes["Send Manager Result Photo"]["parameters"]["inlineKeyboard"] = {
            "rows": [
                {
                    "row": {
                        "buttons": [
                            {
                                "text": "📄 Создать КП (PDF)",
                                "additionalFields": {
                                    "callback_data": "create_kp"
                                }
                            }
                        ]
                    }
                },
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
                                        "url": "={{ ($env.WEBHOOK_URL ? $env.WEBHOOK_URL.replace(/\\/+$/, '') : 'http://localhost:8088') + '/app/index.html' }}"
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }
        print("✅ Updated 'Send Manager Result Photo' inline keyboard with [📄 Создать КП (PDF)], [📊 Скачать презентацию (PDF)], [🔄 Примерить другой диспенсер]")

    # 2. Add 'Render & Send Commercial Proposal' HTTP node
    kp_node_name = "Render & Send Commercial Proposal"
    kp_node = {
        "parameters": {
            "method": "POST",
            "url": "http://dashboard_api:8000/api/manager/generate-kp",
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
            "jsonBody": "={{ JSON.stringify({\n  telegram_id: $('Telegram Trigger').first()?.json?.callback_query ? $('Telegram Trigger').first().json.callback_query.from.id : ($('Telegram Trigger').first()?.json?.message ? $('Telegram Trigger').first().json.message.from.id : ($json.from ? $json.from.id : 0)),\n  chat_id: $('Telegram Trigger').first()?.json?.callback_query ? ($('Telegram Trigger').first().json.callback_query.message ? $('Telegram Trigger').first().json.callback_query.message.chat.id : $('Telegram Trigger').first().json.callback_query.from.id) : ($('Telegram Trigger').first()?.json?.message ? $('Telegram Trigger').first().json.message.chat.id : ($json.chat ? $json.chat.id : 0)),\n  callback_query_id: $('Telegram Trigger').first()?.json?.callback_query ? $('Telegram Trigger').first().json.callback_query.id : undefined,\n  send_to_telegram: true\n}) }}",
            "options": {}
        },
        "id": "node-render-send-kp",
        "name": kp_node_name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [
            1120,
            680
        ]
    }

    if kp_node_name not in nodes:
        wf["nodes"].append(kp_node)
        print(f"✅ Added node: '{kp_node_name}'")
    else:
        for idx, n in enumerate(wf["nodes"]):
            if n["name"] == kp_node_name:
                wf["nodes"][idx] = kp_node
        print(f"✅ Updated existing node: '{kp_node_name}'")

    # 3. Update 'Route by Event Type' Switch node
    if "Route by Event Type" in nodes:
        switch_node = nodes["Route by Event Type"]
        rules = switch_node["parameters"]["rules"]["values"]

        # Expression detecting create_kp
        expr = """={{ ($json.callback_query?.data === 'create_kp' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'create_kp' || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/kp')) ? 'create_kp' : (($json.callback_query?.data === 'download_presentation' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'download_presentation' || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/pdf') || ($json.message?.text || $('Telegram Trigger').first()?.json?.message?.text || '').startsWith('/presentation')) ? 'download_presentation' : (($json.callback_query?.data === 'change_dispenser' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'change_dispenser' || $json.callback_query?.data === 'select_other_dispenser' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'select_other_dispenser') ? 'change_dispenser' : (($json.callback_query?.data === 'restore_previous_montage' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'restore_previous_montage' || $json.callback_query?.data === 'undo_dispenser_change' || $('Telegram Trigger').first()?.json?.callback_query?.data === 'undo_dispenser_change') ? 'restore_previous_montage' : (($json.message?.web_app_data?.data || $('Telegram Trigger').first()?.json?.message?.web_app_data?.data || $('Telegram Trigger').item?.json?.message?.web_app_data?.data) ? 'web_app_select' : (((($json.message?.photo || $('Telegram Trigger').first()?.json?.message?.photo) || (($json.message?.document || $('Telegram Trigger').first()?.json?.message?.document) && (($json.message?.document?.mime_type || $('Telegram Trigger').first()?.json?.message?.document?.mime_type) || '').startsWith('image/')))) ? 'photo' : (($json.callback_query || $('Telegram Trigger').first()?.json?.callback_query || $('Telegram Trigger').item?.json?.callback_query) ? 'callback' : 'other')))))) }}"""

        # Update expression across existing rules
        for r in rules:
            for c in r.get("conditions", {}).get("conditions", []):
                c["leftValue"] = expr

        # Check if create_kp rule already exists
        has_kp_rule = any(r.get("outputKey") == "create_kp" for r in rules)
        if not has_kp_rule:
            kp_rule = {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "leftValue": "",
                        "typeValidation": "strict",
                        "version": 2
                    },
                    "conditions": [
                        {
                            "operator": {
                                "operation": "equals",
                                "type": "string"
                            },
                            "rightValue": "create_kp",
                            "id": "rule-create-kp",
                            "leftValue": expr
                        }
                    ],
                    "combinator": "and"
                },
                "renameOutput": True,
                "outputKey": "create_kp"
            }
            # Insert create_kp branch before callback/fallback
            rules.append(kp_rule)
            print("✅ Added 'create_kp' rule to 'Route by Event Type' Switch")

        # Connect Switch branch to 'Render & Send Commercial Proposal'
        kp_output_idx = len(rules) - 1
        for idx, r in enumerate(rules):
            if r.get("outputKey") == "create_kp":
                kp_output_idx = idx
                break

        switch_conns = connections.setdefault("Route by Event Type", {}).setdefault("main", [])
        while len(switch_conns) <= kp_output_idx:
            switch_conns.append([])

        switch_conns[kp_output_idx] = [
            {
                "node": kp_node_name,
                "type": "main",
                "index": 0
            }
        ]
        print(f"✅ Connected 'Route by Event Type' branch {kp_output_idx} to '{kp_node_name}'")

    # Save to JSON
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump([wf] if is_array else wf, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved workflow JSON: {workflow_path}")

    # 4. Sync into n8n Postgres DB
    db_user = os.getenv("POSTGRES_USER", "tork_admin")
    db_pass = os.getenv("POSTGRES_PASSWORD", "supersecret_tork_kz_pass")
    db_name = os.getenv("POSTGRES_DB", "tork_bot_db")
    db_port = int(os.getenv("POSTGRES_PORT", 5433))

    for port_cand in [db_port, 5432, 5433]:
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=port_cand,
                user=db_user,
                password=db_pass,
                dbname=db_name,
                connect_timeout=3
            )
            with conn.cursor() as cur:
                nodes_json = json.dumps(wf.get("nodes", []), ensure_ascii=False)
                conns_json = json.dumps(wf.get("connections", {}), ensure_ascii=False)
                cur.execute(
                    """
                    UPDATE workflow_entity
                    SET nodes = %s::json,
                        connections = %s::json,
                        "updatedAt" = NOW()
                    WHERE name ILIKE '%%tork%%' OR name ILIKE '%%bot%%' OR id = '1';
                    """,
                    (nodes_json, conns_json)
                )
                updated_rows = cur.rowcount
                conn.commit()
                print(f"✅ Successfully synced workflow to n8n database (port {port_cand}, updated {updated_rows} row(s))")
            conn.close()
            break
        except Exception as e:
            pass

if __name__ == "__main__":
    update_workflow()
