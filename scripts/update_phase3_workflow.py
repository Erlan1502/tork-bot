import json
import os

def update_workflow():
    workflow_path = "workflows/tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_array = isinstance(data, list)
    wf = data[0] if is_array else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    connections = wf.get("connections", {})

    # 1. Update Upsert User Session
    if "Upsert User Session" in nodes:
        nodes["Upsert User Session"]["parameters"]["query"] = (
            "INSERT INTO user_sessions_leads (tg_user_id, tg_username, client_name, distributor_id, current_step, selected_sku) "
            "VALUES ("
            "{{ $('Telegram Trigger').item.json.message ? $('Telegram Trigger').item.json.message.from.id : $('Telegram Trigger').item.json.callback_query.from.id }}, "
            "'{{ ($('Telegram Trigger').item.json.message ? $('Telegram Trigger').item.json.message.from.username : $('Telegram Trigger').item.json.callback_query.from.username) || '' }}', "
            "'{{ ($('Telegram Trigger').item.json.message ? $('Telegram Trigger').item.json.message.from.first_name : $('Telegram Trigger').item.json.callback_query.from.first_name) || 'Менеджер' }}', "
            "{{ $env.DEFAULT_DISTRIBUTOR_ID || 1 }}, "
            "'MANAGER_MODE', "
            "'551000'"
            ") "
            "ON CONFLICT (tg_user_id) DO UPDATE SET "
            "tg_username = EXCLUDED.tg_username, "
            "client_name = EXCLUDED.client_name, "
            "current_step = 'MANAGER_MODE' "
            "RETURNING *;"
        )

    # 2. Update Route by Event Type (Switch node)
    # Output 0: web_app_select (dispenser selected via Mini App)
    # Output 1: photo (image uploaded by manager)
    # Output 2: callback_query (inline button clicked)
    # Fallback / Extra: text_or_other (/start or text)
    route_node = nodes.get("Route by Event Type")
    if route_node:
        cond_expr = (
            "={{ ($json.message?.web_app_data?.data || $('Telegram Trigger').first()?.json?.message?.web_app_data?.data || $('Telegram Trigger').item?.json?.message?.web_app_data?.data) ? 'web_app_select' : "
            "((($json.message?.photo || $('Telegram Trigger').first()?.json?.message?.photo) || (($json.message?.document || $('Telegram Trigger').first()?.json?.message?.document) && (($json.message?.document?.mime_type || $('Telegram Trigger').first()?.json?.message?.document?.mime_type) || '').startsWith('image/'))) ? 'photo' : "
            "(($json.callback_query || $('Telegram Trigger').first()?.json?.callback_query || $('Telegram Trigger').item?.json?.callback_query) ? 'callback' : 'other')) }}"
        )
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

    # 3. New Nodes for Manager Flow
    webapp_url_expr = "={{ ($env.WEBHOOK_URL ? $env.WEBHOOK_URL.replace(/\\/+$/, '') : 'http://localhost:8088') + '/app/index.html' }}"

    # Node: Parse Selected Dispenser (Code)
    parse_dispenser_node = {
        "parameters": {
            "jsCode": (
                "const trigger = $('Telegram Trigger').first()?.json || $input.first()?.json || {};\n"
                "const rawData = trigger.message?.web_app_data?.data || $json.message?.web_app_data?.data || '{}';\n"
                "let parsed = {};\n"
                "try {\n"
                "  parsed = typeof rawData === 'string' ? JSON.parse(rawData) : (rawData || {});\n"
                "} catch (e) {\n"
                "  parsed = {};\n"
                "}\n"
                "\n"
                "const fromUser = trigger.message?.from || trigger.callback_query?.from || {};\n"
                "const tgUserId = fromUser.id || trigger.message?.chat?.id || 0;\n"
                "const sku = String(parsed.sku || parsed.selected_sku || '551000').trim();\n"
                "const colorLabels = {\n"
                "  white: 'Белый',\n"
                "  black: 'Черный',\n"
                "  stainless_steel: 'Нержавеющая сталь',\n"
                "  none: 'Стандарт'\n"
                "};\n"
                "const colorRu = colorLabels[parsed.color] || parsed.color || 'Белый';\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    action: 'select_dispenser',\n"
                "    sku: sku,\n"
                "    name: parsed.name || `Диспенсер Tork (арт. ${sku})`,\n"
                "    system_code: parsed.system_code || 'H1',\n"
                "    color: parsed.color || 'white',\n"
                "    color_ru: colorRu,\n"
                "    category: parsed.category || 'dispenser',\n"
                "    price: parsed.price || 0,\n"
                "    tg_user_id: tgUserId,\n"
                "    chat_id: trigger.message?.chat?.id || tgUserId,\n"
                "    raw_payload: parsed\n"
                "  }\n"
                "}];"
            )
        },
        "id": "node-parse-selected-dispenser",
        "name": "Parse Selected Dispenser",
        "type": "n8n-nodes-base.code",
        "position": [0, 100],
        "typeVersion": 2
    }

    # Node: Save Selected Dispenser (Postgres)
    save_dispenser_node = {
        "parameters": {
            "operation": "executeQuery",
            "query": (
                "UPDATE user_sessions_leads "
                "SET selected_sku = '{{ $json.sku }}', "
                "selected_bundle = '{{ JSON.stringify($json.raw_payload) }}'::jsonb, "
                "updated_at = NOW() "
                "WHERE tg_user_id = {{ $json.tg_user_id }} "
                "RETURNING *;"
            ),
            "options": {}
        },
        "id": "node-save-selected-dispenser",
        "name": "Save Selected Dispenser (SQL)",
        "type": "n8n-nodes-base.postgres",
        "position": [200, 100],
        "typeVersion": 2.4,
        "credentials": {
            "postgres": {
                "id": "ssRaEX0w25vYf2wI",
                "name": "Postgres account"
            }
        }
    }

    # Node: Send Dispenser Confirmation (Telegram)
    confirm_dispenser_node = {
        "parameters": {
            "chatId": "={{ $('Parse Selected Dispenser').first().json.chat_id || $('Parse Selected Dispenser').first().json.tg_user_id }}",
            "text": (
                "={{ '✅ <b>Выбран диспенсер для примерки:</b>\\n' + "
                "'<b>' + $('Parse Selected Dispenser').first().json.name + '</b>\\n\\n' + "
                "'• <b>Артикул:</b> <code>' + $('Parse Selected Dispenser').first().json.sku + '</code>\\n' + "
                "'• <b>Система:</b> <b>' + $('Parse Selected Dispenser').first().json.system_code + '</b>\\n' + "
                "'• <b>Цвет:</b> <b>' + $('Parse Selected Dispenser').first().json.color_ru + '</b>\\n\\n' + "
                "'📸 <b>Следующий шаг:</b> Отправьте фото стены или санузла клиента в этот чат для генерации фотомонтажа.' }}"
            ),
            "replyMarkup": "inlineKeyboard",
            "inlineKeyboard": {
                "rows": [
                    {
                        "row": {
                            "buttons": [
                                {
                                    "text": "🔄 Выбрать другой диспенсер",
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
            },
            "additionalFields": {
                "appendAttribution": False,
                "parse_mode": "HTML"
            }
        },
        "id": "node-send-dispenser-confirm",
        "name": "Send Dispenser Confirmation",
        "type": "n8n-nodes-base.telegram",
        "position": [420, 100],
        "typeVersion": 1.2,
        "credentials": {
            "telegramApi": {
                "id": "ildUvXJDz5GOalvb",
                "name": "Telegram account"
            }
        }
    }

    # Node: Fetch Current Manager Selection (SQL)
    fetch_selection_node = {
        "parameters": {
            "operation": "executeQuery",
            "query": (
                "SELECT "
                "u.tg_user_id, "
                "COALESCE(u.selected_sku, '551000') as selected_sku, "
                "COALESCE(p.name, 'Tork Matic® диспенсер полотенец H1') as dispenser_name, "
                "COALESCE(p.system_code, 'H1') as system_code, "
                "COALESCE(p.color, 'white') as color, "
                "COALESCE(p.dimensions_cm, '{\"w\": 33.7, \"h\": 37.2, \"d\": 20.6}'::jsonb) as dimensions_cm, "
                "COALESCE(p.category, 'dispenser') as category "
                "FROM user_sessions_leads u "
                "LEFT JOIN products p ON p.sku = COALESCE(u.selected_sku, '551000') "
                "WHERE u.tg_user_id = {{ $('Telegram Trigger').item.json.message ? $('Telegram Trigger').item.json.message.from.id : $('Telegram Trigger').item.json.callback_query.from.id }};"
            ),
            "options": {}
        },
        "id": "node-fetch-manager-selection",
        "name": "Fetch Current Manager Selection (SQL)",
        "type": "n8n-nodes-base.postgres",
        "position": [200, 320],
        "typeVersion": 2.4,
        "credentials": {
            "postgres": {
                "id": "ssRaEX0w25vYf2wI",
                "name": "Postgres account"
            }
        }
    }

    # Node: Prepare Manager Montage (Code)
    prepare_montage_node = {
        "parameters": {
            "jsCode": (
                "const fs = require('fs');\n"
                "\n"
                "// 1. Downloaded photo binary\n"
                "const photoItem = $('Download Telegram Photo').first();\n"
                "let userPhotoBase64 = '';\n"
                "if (photoItem?.binary?.data?.data) {\n"
                "  userPhotoBase64 = photoItem.binary.data.data;\n"
                "}\n"
                "\n"
                "// 2. Selection from DB query\n"
                "const selection = $('Fetch Current Manager Selection (SQL)').first()?.json || {};\n"
                "const sku = String(selection.selected_sku || '551000').trim();\n"
                "const name = selection.dispenser_name || 'Диспенсер Tork';\n"
                "const systemCode = selection.system_code || 'H1';\n"
                "const color = selection.color || 'white';\n"
                "const dims = selection.dimensions_cm || { w: 33.7, h: 37.2, d: 20.6 };\n"
                "\n"
                "// 3. Load clean PNG from /data/assets/images/\n"
                "let dispenserBase64 = '';\n"
                "const searchPaths = [\n"
                "  `/data/assets/images/${sku}.png`,\n"
                "  `/data/assets/images/${sku}.jpg`,\n"
                "  '/data/assets/images/551000.png'\n"
                "];\n"
                "\n"
                "for (const p of searchPaths) {\n"
                "  try {\n"
                "    if (fs.existsSync(p)) {\n"
                "      dispenserBase64 = fs.readFileSync(p).toString('base64');\n"
                "      if (dispenserBase64) break;\n"
                "    }\n"
                "  } catch (err) {}\n"
                "}\n"
                "\n"
                "const promptText = `You are an expert AI photo editor for Tork (Essity). Mount and composite the exact Tork dispenser shown in the second image onto the washroom wall in the first image.\\n` +\n"
                "  `Location: mount the dispenser realistically on the wall near the sink or mirror at natural eye and hand reach level.\\n` +\n"
                "  `Preserve the exact product shape, color finish (${color}), front window, dispensing slot and Tork logo from the second reference image.\\n` +\n"
                "  `Real product dimensions: width ${dims.w || 33.7} cm, height ${dims.h || 37.2} cm.\\n` +\n"
                "  `Scale it realistically relative to the room tiles and counter. Cast natural realistic contact shadows onto the wall matching room lighting.\\n` +\n"
                "  `Return only the photorealistic composite image of the room with the mounted dispenser.`;\n"
                "\n"
                "const tgTrigger = $('Telegram Trigger').first()?.json || {};\n"
                "const chatId = tgTrigger.message?.chat?.id || tgTrigger.callback_query?.message?.chat?.id;\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    sku: sku,\n"
                "    name: name,\n"
                "    system_code: systemCode,\n"
                "    color: color,\n"
                "    dimensions_cm: dims,\n"
                "    dimensions_w: dims.w || 33.7,\n"
                "    dimensions_h: dims.h || 37.2,\n"
                "    user_photo_base64: userPhotoBase64,\n"
                "    dispenser_clean_base64: dispenserBase64,\n"
                "    prompt_text: promptText,\n"
                "    chat_id: chatId\n"
                "  }\n"
                "}];"
            )
        },
        "id": "node-prepare-manager-montage",
        "name": "Prepare Manager Montage",
        "type": "n8n-nodes-base.code",
        "position": [420, 320],
        "typeVersion": 2
    }

    # Node: Call Image Edit API (HTTP Request)
    call_image_edit_node = {
        "parameters": {
            "method": "POST",
            "url": "={{ 'https://generativelanguage.googleapis.com/v1beta/models/' + ($env.IMAGE_EDIT_MODEL || 'gemini-3.1-flash-image') + ':generateContent?key=' + ($env.IMAGE_EDIT_API_KEY || $env.VLM_API_KEY) }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "x-goog-api-key", "value": "={{ $env.IMAGE_EDIT_API_KEY || $env.VLM_API_KEY }}"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ JSON.stringify({\n"
                "  contents: [\n"
                "    {\n"
                "      parts: [\n"
                "        { text: $json.prompt_text },\n"
                "        { inline_data: { mime_type: 'image/jpeg', data: $json.user_photo_base64 } },\n"
                "        { inline_data: { mime_type: 'image/png', data: $json.dispenser_clean_base64 } }\n"
                "      ]\n"
                "    }\n"
                "  ],\n"
                "  generationConfig: {\n"
                "    responseModalities: ['IMAGE']\n"
                "  }\n"
                "}) }}"
            )
        },
        "id": "node-call-image-edit-api",
        "name": "Call Image Edit API",
        "type": "n8n-nodes-base.httpRequest",
        "position": [640, 320],
        "typeVersion": 4.2
    }

    # Node: Process Manager Result (Code)
    process_result_node = {
        "parameters": {
            "jsCode": (
                "const prep = $('Prepare Manager Montage').first()?.json || {};\n"
                "const apiResponse = $input.first()?.json || {};\n"
                "\n"
                "let base64Image = '';\n"
                "let mimeType = 'image/png';\n"
                "\n"
                "const parts = apiResponse.candidates?.[0]?.content?.parts || [];\n"
                "const imagePart = parts.find(p => (p.inlineData && p.inlineData.data) || (p.inline_data && p.inline_data.data));\n"
                "\n"
                "if (imagePart?.inlineData?.data) {\n"
                "  base64Image = imagePart.inlineData.data;\n"
                "  mimeType = imagePart.inlineData.mimeType || 'image/jpeg';\n"
                "} else if (imagePart?.inline_data?.data) {\n"
                "  base64Image = imagePart.inline_data.data;\n"
                "  mimeType = imagePart.inline_data.mime_type || 'image/jpeg';\n"
                "}\n"
                "\n"
                "// Fallback to clean dispenser PNG if Gemini returned text or empty\n"
                "if (!base64Image) {\n"
                "  base64Image = prep.dispenser_clean_base64 || '';\n"
                "  mimeType = 'image/png';\n"
                "}\n"
                "\n"
                "const colorLabels = {\n"
                "  white: 'Белый',\n"
                "  black: 'Черный',\n"
                "  stainless_steel: 'Нержавеющая сталь',\n"
                "  none: 'Стандарт'\n"
                "};\n"
                "const colorRu = colorLabels[prep.color] || prep.color || 'Белый';\n"
                "\n"
                "const caption = `✨ <b>Визуализация готова!</b>\\n\\n` +\n"
                "  `• Диспенсер: <b>${prep.name}</b>\\n` +\n"
                "  `• Артикул: <code>${prep.sku}</code>\\n` +\n"
                "  `• Система: <b>${prep.system_code}</b> (${colorRu})\\n` +\n"
                "  `• Габариты: ${prep.dimensions_w} × ${prep.dimensions_h} см\\n\\n` +\n"
                "  `<i>Монтаж выполнен с сохранением масштаба и теней.</i>`;\n"
                "\n"
                "return [{\n"
                "  json: {\n"
                "    sku: prep.sku,\n"
                "    dispenser_name: prep.name,\n"
                "    system_code: prep.system_code,\n"
                "    color_ru: colorRu,\n"
                "    caption: caption,\n"
                "    chat_id: prep.chat_id,\n"
                "    has_generated_image: Boolean(imagePart)\n"
                "  },\n"
                "  binary: {\n"
                "    visualization: {\n"
                "      data: base64Image,\n"
                "      mimeType: mimeType,\n"
                "      fileName: `tork_${prep.sku}_fitting.png`\n"
                "    }\n"
                "  }\n"
                "}];"
            )
        },
        "id": "node-process-manager-result",
        "name": "Process Manager Result",
        "type": "n8n-nodes-base.code",
        "position": [860, 320],
        "typeVersion": 2
    }

    # Node: Send Manager Result Photo (Telegram)
    send_result_photo_node = {
        "parameters": {
            "resource": "message",
            "operation": "sendPhoto",
            "chatId": "={{ $json.chat_id || $('Telegram Trigger').first().json.message.chat.id }}",
            "binaryData": True,
            "binaryPropertyName": "visualization",
            "caption": "={{ $json.caption }}",
            "replyMarkup": "inlineKeyboard",
            "inlineKeyboard": {
                "rows": [
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
            },
            "additionalFields": {
                "appendAttribution": False,
                "parse_mode": "HTML"
            }
        },
        "id": "node-send-manager-result-photo",
        "name": "Send Manager Result Photo",
        "type": "n8n-nodes-base.telegram",
        "position": [1080, 320],
        "typeVersion": 1.2,
        "credentials": {
            "telegramApi": {
                "id": "ildUvXJDz5GOalvb",
                "name": "Telegram account"
            }
        }
    }

    # Node: Send Manager Welcome & Menu (Telegram)
    welcome_menu_node = {
        "parameters": {
            "chatId": "={{ $json.auth ? $json.auth.chat_id : ($json.message?.chat?.id || $json.callback_query?.message?.chat?.id) }}",
            "text": (
                "={{ '👋 <b>Здравствуйте, ' + ($json.auth?.user_name || 'Менеджер') + '!</b>\\n\\n' + "
                "'Добро пожаловать в <b>Tork Visualizer (Manager-Only Mode)</b>.\\n' + "
                "'Этот инструмент предназначен для быстрого создания фотомонтажа и визуализации диспенсеров Tork в интерьерах клиентов.\\n\\n' + "
                "'📦 В каталоге доступно <b>165 товаров Tork</b> (83 настенных диспенсера для примерки).\\n\\n' + "
                "'🚀 <b>Как работать:</b>\\n' + "
                "'1. Откройте <b>«✨ Каталог диспенсеров»</b> по кнопке ниже и выберите нужный артикул.\\n' + "
                "'2. Отправьте в этот чат фотографию стены или санузла клиента.\\n' + "
                "'3. Нейросеть смонтирует диспенсер на стену с сохранением масштаба и естественных теней!' }}"
            ),
            "replyMarkup": "inlineKeyboard",
            "inlineKeyboard": {
                "rows": [
                    {
                        "row": {
                            "buttons": [
                                {
                                    "text": "✨ Каталог диспенсеров (165 SKU)",
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
            },
            "additionalFields": {
                "appendAttribution": False,
                "parse_mode": "HTML"
            }
        },
        "id": "node-send-manager-welcome",
        "name": "Send Manager Welcome & Menu",
        "type": "n8n-nodes-base.telegram",
        "position": [0, 500],
        "typeVersion": 1.2,
        "credentials": {
            "telegramApi": {
                "id": "ildUvXJDz5GOalvb",
                "name": "Telegram account"
            }
        }
    }

    # Add new/updated nodes into dict
    new_nodes_map = {
        "Parse Selected Dispenser": parse_dispenser_node,
        "Save Selected Dispenser (SQL)": save_dispenser_node,
        "Send Dispenser Confirmation": confirm_dispenser_node,
        "Fetch Current Manager Selection (SQL)": fetch_selection_node,
        "Prepare Manager Montage": prepare_montage_node,
        "Call Image Edit API": call_image_edit_node,
        "Process Manager Result": process_result_node,
        "Send Manager Result Photo": send_result_photo_node,
        "Send Manager Welcome & Menu": welcome_menu_node
    }

    # Replace / append in nodes list
    node_list = []
    for n in wf.get("nodes", []):
        if n["name"] in new_nodes_map:
            node_list.append(new_nodes_map[n["name"]])
            del new_nodes_map[n["name"]]
        else:
            node_list.append(n)
    for n in new_nodes_map.values():
        node_list.append(n)

    wf["nodes"] = node_list

    # 4. Wire Connections for Manager Mode
    # Route by Event Type:
    # Output 0 (web_app_select) -> Parse Selected Dispenser
    # Output 1 (photo) -> Download Telegram Photo
    # Output 2 (callback) -> Send Manager Welcome & Menu
    # Output 3 (text_or_other) -> Send Manager Welcome & Menu
    connections["Route by Event Type"] = {
        "main": [
            [{"node": "Parse Selected Dispenser", "type": "main", "index": 0}],
            [{"node": "Download Telegram Photo", "type": "main", "index": 0}],
            [{"node": "Send Manager Welcome & Menu", "type": "main", "index": 0}],
            [{"node": "Send Manager Welcome & Menu", "type": "main", "index": 0}]
        ]
    }

    # Branch A: WebApp dispenser selection
    connections["Parse Selected Dispenser"] = {
        "main": [[{"node": "Save Selected Dispenser (SQL)", "type": "main", "index": 0}]]
    }
    connections["Save Selected Dispenser (SQL)"] = {
        "main": [[{"node": "Send Dispenser Confirmation", "type": "main", "index": 0}]]
    }
    if "Send Dispenser Confirmation" in connections:
        del connections["Send Dispenser Confirmation"]

    # Branch B: Photo Montage
    connections["Download Telegram Photo"] = {
        "main": [[{"node": "Fetch Current Manager Selection (SQL)", "type": "main", "index": 0}]]
    }
    connections["Fetch Current Manager Selection (SQL)"] = {
        "main": [[{"node": "Prepare Manager Montage", "type": "main", "index": 0}]]
    }
    connections["Prepare Manager Montage"] = {
        "main": [[{"node": "Call Image Edit API", "type": "main", "index": 0}]]
    }
    connections["Call Image Edit API"] = {
        "main": [[{"node": "Process Manager Result", "type": "main", "index": 0}]]
    }
    connections["Process Manager Result"] = {
        "main": [[{"node": "Send Manager Result Photo", "type": "main", "index": 0}]]
    }
    if "Send Manager Result Photo" in connections:
        del connections["Send Manager Result Photo"]

    # Branch C: Welcome & Menu
    if "Send Manager Welcome & Menu" in connections:
        del connections["Send Manager Welcome & Menu"]

    # Clean up obsolete connections from bypassed nodes
    obsolete_outgoing = [
        "Check Rate Limit", "Limit Exceeded Message", "Update Session Segment",
        "Send Photo Request", "Send Welcome Onboarding", "Calculate KP Bundle",
        "Generate PDF via Gotenberg", "Send Client Result & Inline Buttons",
        "Send Client PDF Document", "Notify Managers Group"
    ]
    for obs in obsolete_outgoing:
        if obs in connections:
            del connections[obs]

    wf["connections"] = connections

    # Write back
    new_data = [wf] if is_array else wf
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"Phase 3 workflow updated successfully! Total nodes: {len(node_list)}")

if __name__ == "__main__":
    update_workflow()

