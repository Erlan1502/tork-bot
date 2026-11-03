import json
import os

def update_docker_compose():
    path = "docker-compose.yml"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    target = "      - MANAGER_CHAT_ID=${MANAGER_CHAT_ID}\n"
    addition = "      - MANAGER_CHAT_ID=${MANAGER_CHAT_ID}\n      - ALLOWED_TELEGRAM_IDS=${ALLOWED_TELEGRAM_IDS}\n"
    
    if "ALLOWED_TELEGRAM_IDS" not in content:
        if target in content:
            content = content.replace(target, addition, 1)
        elif "MANAGER_CHAT_ID=${MANAGER_CHAT_ID}" in content:
            content = content.replace(
                "      - MANAGER_CHAT_ID=${MANAGER_CHAT_ID}\r\n",
                "      - MANAGER_CHAT_ID=${MANAGER_CHAT_ID}\r\n      - ALLOWED_TELEGRAM_IDS=${ALLOWED_TELEGRAM_IDS}\r\n",
                1
            )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated docker-compose.yml")
    else:
        print("docker-compose.yml already contains ALLOWED_TELEGRAM_IDS")

def update_workflow():
    workflow_path = "workflows/tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_array = isinstance(data, list)
    wf = data[0] if is_array else data
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    # 1. Define JS code for Check Manager Whitelist
    whitelist_js = (
        "const triggerJson = $('Telegram Trigger').first()?.json || $input.first()?.json || $json || {};\n"
        "const message = triggerJson.message || triggerJson.callback_query?.message;\n"
        "const fromUser = triggerJson.message?.from || triggerJson.callback_query?.from;\n"
        "\n"
        "const userId = fromUser?.id != null ? String(fromUser.id).trim() : '';\n"
        "const chatId = message?.chat?.id != null ? String(message.chat.id).trim() : (userId || '');\n"
        "const username = fromUser?.username ? `@${fromUser.username}` : '';\n"
        "const fullName = [fromUser?.first_name, fromUser?.last_name].filter(Boolean).join(' ') || username || 'Сотрудник';\n"
        "\n"
        "let allowedRaw = '';\n"
        "try {\n"
        "  if (typeof $env !== 'undefined' && $env.ALLOWED_TELEGRAM_IDS) {\n"
        "    allowedRaw = String($env.ALLOWED_TELEGRAM_IDS);\n"
        "  } else if (typeof process !== 'undefined' && process.env && process.env.ALLOWED_TELEGRAM_IDS) {\n"
        "    allowedRaw = String(process.env.ALLOWED_TELEGRAM_IDS);\n"
        "  }\n"
        "} catch (e) {\n"
        "  allowedRaw = '';\n"
        "}\n"
        "\n"
        "allowedRaw = allowedRaw.trim();\n"
        "const allowedList = allowedRaw\n"
        "  ? allowedRaw.split(/[\\s,;]+/).map(s => s.trim()).filter(Boolean)\n"
        "  : [];\n"
        "\n"
        "// Если список пуст — режим настройки (доступ открыт)\n"
        "// Если список заполнен — проверяем userId или chatId\n"
        "const isAllowed = (allowedList.length === 0) ||\n"
        "  (userId && allowedList.includes(userId)) ||\n"
        "  (chatId && allowedList.includes(chatId));\n"
        "\n"
        "return [{\n"
        "  json: {\n"
        "    ...triggerJson,\n"
        "    auth: {\n"
        "      user_id: userId,\n"
        "      chat_id: chatId,\n"
        "      user_name: fullName,\n"
        "      username: username,\n"
        "      is_allowed: isAllowed,\n"
        "      whitelist_configured: allowedList.length > 0,\n"
        "      checked_at: new Date().toISOString()\n"
        "    }\n"
        "  }\n"
        "}];"
    )

    # 2. Define node structures
    whitelist_node = {
        "parameters": {
            "jsCode": whitelist_js
        },
        "id": "node-check-manager-whitelist",
        "name": "Check Manager Whitelist",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-780, 208]
    }

    is_allowed_node = {
        "parameters": {
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
                            "type": "boolean"
                        },
                        "rightValue": True,
                        "id": "cond-is-allowed",
                        "leftValue": "={{ $json.auth ? $json.auth.is_allowed : true }}"
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": "node-is-user-allowed",
        "name": "Is User Allowed?",
        "type": "n8n-nodes-base.if",
        "position": [-680, 208],
        "typeVersion": 2
    }

    access_denied_node = {
        "parameters": {
            "chatId": "={{ $json.auth ? $json.auth.chat_id : ($json.message?.chat?.id || $json.callback_query?.message?.chat?.id) }}",
            "text": "⛔️ *Доступ ограничен (Manager-Only Mode)*\n\nЭтот бот предназначен исключительно для авторизованных менеджеров и сотрудников Tork.\n\n👤 *Ваш профиль:*\n• Имя: {{ $json.auth ? $json.auth.user_name : 'Сотрудник' }}\n• Telegram ID: `{{ $json.auth ? $json.auth.user_id : 'Не определен' }}`\n\nДля получения доступа передайте ваш Telegram ID администратору.",
            "additionalFields": {
                "appendAttribution": False,
                "parse_mode": "Markdown"
            }
        },
        "id": "node-send-access-denied",
        "name": "Send Access Denied",
        "type": "n8n-nodes-base.telegram",
        "position": [-680, 40],
        "typeVersion": 1.2,
        "credentials": {
            "telegramApi": {
                "id": "ildUvXJDz5GOalvb",
                "name": "Telegram account"
            }
        }
    }

    # Remove previous versions of these nodes if present
    target_names = {"Check Manager Whitelist", "Is User Allowed?", "Send Access Denied"}
    nodes = [n for n in nodes if n.get("name") not in target_names]

    # Add the 3 nodes
    nodes.extend([whitelist_node, is_allowed_node, access_denied_node])
    wf["nodes"] = nodes

    # 3. Update connections
    # Filter Private Chat Only -> Check Manager Whitelist
    connections["Filter Private Chat Only"] = {
        "main": [
            [
                {
                    "node": "Check Manager Whitelist",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Check Manager Whitelist -> Is User Allowed?
    connections["Check Manager Whitelist"] = {
        "main": [
            [
                {
                    "node": "Is User Allowed?",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Is User Allowed? ->
    # Output 0 (True / Allowed) -> Check Media Type
    # Output 1 (False / Denied) -> Send Access Denied
    connections["Is User Allowed?"] = {
        "main": [
            [
                {
                    "node": "Check Media Type",
                    "type": "main",
                    "index": 0
                }
            ],
            [
                {
                    "node": "Send Access Denied",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # Send Access Denied -> terminal node (no outgoing connections)
    if "Send Access Denied" in connections:
        del connections["Send Access Denied"]

    wf["connections"] = connections

    new_data = [wf] if is_array else wf
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"Updated workflow successfully. Total nodes now: {len(nodes)}")

if __name__ == "__main__":
    update_docker_compose()
    update_workflow()

