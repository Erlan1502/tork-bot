import json
import psycopg2

workflow_path = "workflows/tork_bot_workflow.json"
with open(workflow_path, "r", encoding="utf-8") as f:
    workflows_data = json.load(f)

# The file contains an array with one workflow object
wf = workflows_data[0] if isinstance(workflows_data, list) else workflows_data

nodes = wf["nodes"]
connections = wf["connections"]

# 1. Update Route by Event Type
route_node = next((n for n in nodes if n["name"] == "Route by Event Type"), None)
if route_node:
    cond_expr = "={{ ($json.message?.web_app_data?.data || $('Telegram Trigger').first()?.json?.message?.web_app_data?.data || $('Telegram Trigger').item?.json?.message?.web_app_data?.data) ? 'web_app_order' : (($json.callback_query || $('Telegram Trigger').first()?.json?.callback_query || $('Telegram Trigger').item?.json?.callback_query) ? 'callback' : ((($json.message?.photo || $('Telegram Trigger').first()?.json?.message?.photo) || (($json.message?.document || $('Telegram Trigger').first()?.json?.message?.document) && (($json.message?.document?.mime_type || $('Telegram Trigger').first()?.json?.message?.document?.mime_type) || '').startsWith('image/'))) ? 'photo' : 'other')) }}"
    
    route_node["parameters"]["rules"]["values"] = [
        {
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
                        "rightValue": "web_app_order",
                        "id": "rule-web-app-order",
                        "leftValue": cond_expr
                    }
                ],
                "combinator": "and"
            },
            "renameOutput": True,
            "outputKey": "web_app_order"
        },
        {
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
                        "rightValue": "callback",
                        "id": "rule-callback",
                        "leftValue": cond_expr
                    }
                ],
                "combinator": "and"
            },
            "renameOutput": True,
            "outputKey": "callback_query"
        },
        {
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
                        "rightValue": "photo",
                        "id": "rule-photo",
                        "leftValue": cond_expr
                    }
                ],
                "combinator": "and"
            },
            "renameOutput": True,
            "outputKey": "photo"
        }
    ]
    route_node["parameters"]["options"] = {
        "fallbackOutput": "extra",
        "renameFallbackOutput": "text_or_other"
    }

# 2. Add New Nodes
existing_names = {
    "Parse WebApp Order & Match Distributor",
    "Prepare Gotenberg Payload",
    "Generate PDF via Gotenberg (Order)",
    "Send PDF to Client",
    "Notify Managers Group (Order)",
    "Update Order Session"
}
nodes = [n for n in nodes if n["name"] not in existing_names]

parse_node = {
    "parameters": {
        "jsCode": """const triggerJson = $('Telegram Trigger').first()?.json || {};
const triggerData = triggerJson.message?.web_app_data?.data || $input.first()?.json?.message?.web_app_data?.data || $input.first()?.json?.web_app_data?.data;
let rawData = {};
try {
  rawData = typeof triggerData === 'string' ? JSON.parse(triggerData) : (triggerData || {});
} catch (e) {
  rawData = {};
}

if (!rawData.items && $input.first()?.json?.items) {
  rawData = $input.first().json;
}

// Сгенерировать номер и дату КП
const kp_number = 'TKZ-' + Date.now().toString().slice(-6);
const kp_date = new Date().toLocaleDateString('ru-RU');

// Определить реквизиты регионального дистрибьютора по полю city
const cityNorm = (rawData.city || '').trim().toLowerCase();
let distributor = {
  distributor_id: 1,
  distributor_name: 'ТОО "Tork Kazakhstan Distribution Astana"',
  distributor_bin: '210540032111',
  distributor_city: 'г. Астана',
  distributor_address: 'г. Астана, район Есиль, ул. Достык, 18, БЦ "Москва", офис 704',
  distributor_phone: '+7 (7172) 79-55-01',
  distributor_email: 'astana@tork-distrib.kz'
};

if (cityNorm.includes('алмат') || cityNorm === 'almaty') {
  distributor = {
    distributor_id: 2,
    distributor_name: 'ТОО "Tork Distribution Almaty"',
    distributor_bin: '190340019882',
    distributor_city: 'г. Алматы',
    distributor_address: 'г. Алматы, пр. Аль-Фараби, 77/7, БЦ "Esentai Tower", блок 2',
    distributor_phone: '+7 (727) 355-88-22',
    distributor_email: 'almaty@tork-distrib.kz'
  };
} else if (cityNorm.includes('шымкент') || cityNorm === 'shymkent') {
  distributor = {
    distributor_id: 3,
    distributor_name: 'ТОО "Tork South Industrial KZ"',
    distributor_bin: '220140045671',
    distributor_city: 'г. Шымкент',
    distributor_address: 'г. Шымкент, Абайский р-н, ул. Байтерекова, 25, БЦ "Орда"',
    distributor_phone: '+7 (7252) 99-44-11',
    distributor_email: 'shymkent@tork-distrib.kz'
  };
}

const items = Array.isArray(rawData.items) ? rawData.items : [];
const itemsSummary = items.map((it, idx) => 
  `${idx + 1}. [${it.sku}] ${it.name} — ${it.qty} шт. x ${Number(it.price || 0).toLocaleString('ru-RU')} ₸ = ${Number(it.line_total || (it.price * it.qty) || 0).toLocaleString('ru-RU')} ₸`
).join('\\n');

const totalAmount = Number(rawData.total_amount || items.reduce((s, i) => s + (Number(i.line_total) || (Number(i.price) * Number(i.qty)) || 0), 0));
const totalAmountFormatted = totalAmount.toLocaleString('ru-RU');

const tgUser = triggerJson.message?.from || {};

return [{
  json: {
    event: rawData.event || 'web_app_order',
    company_name: rawData.company_name || 'ТОО Рассвет',
    bin: rawData.bin || '',
    city: rawData.city || 'Астана',
    client_name: rawData.client_name || '',
    phone: rawData.phone || '',
    items: items,
    total_amount: totalAmount,
    total_amount_formatted: totalAmountFormatted,
    items_summary: itemsSummary,
    kp_number: kp_number,
    kp_date: kp_date,
    ...distributor,
    tg_user_id: tgUser.id || 0,
    tg_username: tgUser.username || ''
  }
}];"""
    },
    "id": "parse-webapp-order",
    "name": "Parse WebApp Order & Match Distributor",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [0, 640]
}

prepare_node = {
    "parameters": {
        "jsCode": """const fs = require('fs');

const rawData = $('Parse WebApp Order & Match Distributor').first()?.json || $input.first().json;
const items = Array.isArray(rawData.items) ? rawData.items : [];

let rowsHtml = '';
items.forEach((item, idx) => {
  const sku = String(item.sku).trim();
  const imgUrl = `http://cdn/images/${sku}.png`;
  const imgTag = `<img src="${imgUrl}" width="34" height="34" style="object-fit:contain; vertical-align:middle; margin-right:8px; border-radius:3px; border:1px solid #E2E8F0; background:#fff;" />`;
  rowsHtml += `
    <tr>
      <td class="text-center">${idx + 1}</td>
      <td><strong>${sku}</strong></td>
      <td><div style="display:flex; align-items:center;">${imgTag}<span>${item.name}</span></div></td>
      <td class="text-center"><span class="badge">${item.system_code || '—'}</span></td>
      <td class="text-center">${item.qty}</td>
      <td class="text-right">${Number(item.price).toLocaleString('ru-RU')} ₸</td>
      <td class="text-right"><strong>${Number(item.line_total).toLocaleString('ru-RU')} ₸</strong></td>
    </tr>
  `;
});

const templatePath = '/data/templates/kp_template.html';
let htmlContent = '';
try {
  htmlContent = fs.readFileSync(templatePath, 'utf8');
} catch (e) {
  htmlContent = '<html><body><h1>Коммерческое предложение Tork</h1></body></html>';
}

const clientNameFormatted = `${rawData.company_name} (контакт: ${rawData.client_name || 'Представитель'})`;
const trafficFormatted = `${items.length} наим.`;
const renderedImageDataUri = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="240" height="160" viewBox="0 0 240 160"><rect width="240" height="160" fill="%23003865"/><text x="50%" y="45%" dominant-baseline="middle" text-anchor="middle" fill="%23ffffff" font-size="24" font-weight="bold" font-family="sans-serif">TORK</text><text x="50%" y="65%" dominant-baseline="middle" text-anchor="middle" fill="%23009FDA" font-size="11" font-family="sans-serif">Официальное КП</text></svg>';
const recommendedColorRu = 'Стандартная комплектация';
const placementInstructionRu = 'Комплектация подобрана согласно спецификации заказчика в каталоге Tork.';
const totalAmountFormatted = Number(rawData.total_amount).toLocaleString('ru-RU');

const templateReplacements = {
  distributor_name: rawData.distributor_name,
  distributor_bin: rawData.distributor_bin,
  distributor_city: rawData.distributor_city,
  distributor_address: rawData.distributor_address,
  distributor_phone: rawData.distributor_phone,
  distributor_email: rawData.distributor_email,
  kp_number: rawData.kp_number,
  kp_date: rawData.kp_date,
  client_name: clientNameFormatted,
  business_segment: rawData.city,
  daily_traffic: trafficFormatted,
  rendered_image_data_uri: renderedImageDataUri,
  recommended_color_ru: recommendedColorRu,
  placement_instruction_ru: placementInstructionRu,
  table_rows_html: rowsHtml,
  total_amount_formatted: totalAmountFormatted
};

let renderedHtml = htmlContent;
for (const [key, val] of Object.entries(templateReplacements)) {
  const reg = new RegExp('\\\\{\\\\{\\\\s*' + key + '\\\\s*\\\\}\\\\}', 'g');
  renderedHtml = renderedHtml.replace(reg, String(val ?? ''));
}

const htmlBuffer = Buffer.from(renderedHtml, 'utf-8');

return [{
  json: {
    ...rawData,
    total_amount_formatted: totalAmountFormatted,
    items_summary: rawData.items_summary,
    table_rows_html: rowsHtml
  },
  binary: {
    files: {
      data: htmlBuffer.toString('base64'),
      mimeType: 'text/html',
      fileName: 'index.html'
    }
  }
}];"""
    },
    "id": "prepare-gotenberg-payload",
    "name": "Prepare Gotenberg Payload",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [224, 640]
}

gotenberg_order_node = {
    "parameters": {
        "method": "POST",
        "url": "http://gotenberg:3000/forms/chromium/convert/html",
        "sendBody": True,
        "contentType": "multipart-form-data",
        "bodyParameters": {
            "parameters": [
                {
                    "parameterType": "formBinaryData",
                    "name": "files",
                    "inputDataFieldName": "files"
                }
            ]
        },
        "options": {
            "response": {
                "response": {
                    "responseFormat": "file",
                    "outputPropertyName": "pdf"
                }
            }
        }
    },
    "onError": "continueRegularOutput",
    "id": "generate-pdf-gotenberg-order",
    "name": "Generate PDF via Gotenberg (Order)",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [448, 640]
}

send_client_caption = "={{ '✅ Ваш заказ успешно принят!\\n\\n📄 Официальное коммерческое предложение № ' + ($json.kp_number || $('Parse WebApp Order & Match Distributor').first().json.kp_number) + ' сформировано и прикреплено к этому сообщению.\\n\\nНаш региональный менеджер свяжется с вами для уточнения деталей поставки.' }}"

send_client_node = {
    "parameters": {
        "resource": "message",
        "operation": "sendDocument",
        "chatId": "={{ $('Telegram Trigger').item.json.message.chat.id }}",
        "binaryData": True,
        "binaryPropertyName": "pdf",
        "caption": send_client_caption,
        "additionalFields": {
            "caption": send_client_caption,
            "fileName": "KP_Tork.pdf",
            "appendAttribution": False
        }
    },
    "onError": "continueRegularOutput",
    "id": "send-pdf-to-client",
    "name": "Send PDF to Client",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [672, 540],
    "credentials": {
        "telegramApi": {
            "id": "ildUvXJDz5GOalvb",
            "name": "Telegram account"
        }
    }
}

notify_managers_caption = "={{ '🚨 Новая заявка из каталога Tork (Казахстан)\\n\\n🏢 Компания: ' + ($json.company_name || $('Parse WebApp Order & Match Distributor').first().json.company_name) + '\\n🔢 БИН/ИИН: ' + ($json.bin || $('Parse WebApp Order & Match Distributor').first().json.bin) + '\\n📍 Город: ' + ($json.city || $('Parse WebApp Order & Match Distributor').first().json.city) + '\\n👤 Контакт: ' + ($json.client_name || $('Parse WebApp Order & Match Distributor').first().json.client_name) + ' (' + ($json.phone || $('Parse WebApp Order & Match Distributor').first().json.phone) + ')\\n💬 Telegram: @' + ($('Telegram Trigger').first().json.message?.from?.username || $('Telegram Trigger').item.json.message.from.username || 'нет') + '\\n\\n📦 Состав заказа:\\n' + ($json.items_summary || $('Parse WebApp Order & Match Distributor').first().json.items_summary) + '\\n\\n💰 Итого: ' + ($json.total_amount_formatted || $('Parse WebApp Order & Match Distributor').first().json.total_amount_formatted) + ' ₸\\n📄 Номер КП: ' + ($json.kp_number || $('Parse WebApp Order & Match Distributor').first().json.kp_number) }}"

notify_managers_node = {
    "parameters": {
        "resource": "message",
        "operation": "sendDocument",
        "chatId": "={{ $env.MANAGER_CHAT_ID }}",
        "binaryData": True,
        "binaryPropertyName": "pdf",
        "caption": notify_managers_caption,
        "additionalFields": {
            "caption": notify_managers_caption,
            "fileName": "KP_Tork.pdf",
            "appendAttribution": False
        }
    },
    "onError": "continueRegularOutput",
    "id": "notify-managers-order",
    "name": "Notify Managers Group (Order)",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [672, 740],
    "credentials": {
        "telegramApi": {
            "id": "ildUvXJDz5GOalvb",
            "name": "Telegram account"
        }
    }
}

update_session_node = {
    "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE user_sessions_leads SET company_name = '{{ ($('Parse WebApp Order & Match Distributor').first().json.company_name || '').replace(/'/g, \"''\") }}', phone = '{{ ($('Parse WebApp Order & Match Distributor').first().json.phone || '').replace(/'/g, \"''\") }}', current_step = 'ORDER_COMPLETED', selected_bundle = '{{ JSON.stringify($('Parse WebApp Order & Match Distributor').first().json.items || []).replace(/'/g, \"''\") }}'::jsonb, distributor_id = {{ $('Parse WebApp Order & Match Distributor').first().json.distributor_id || 1 }}, updated_at = NOW() WHERE tg_user_id = {{ $('Telegram Trigger').first().json.message?.from?.id || $('Parse WebApp Order & Match Distributor').first().json.tg_user_id || 0 }};",
        "options": {}
    },
    "onError": "continueRegularOutput",
    "id": "update-order-session",
    "name": "Update Order Session",
    "type": "n8n-nodes-base.postgres",
    "typeVersion": 2.4,
    "position": [896, 740],
    "credentials": {
        "postgres": {
            "id": "ssRaEX0w25vYf2wI",
            "name": "Postgres account"
        }
    }
}

nodes.extend([
    parse_node,
    prepare_node,
    gotenberg_order_node,
    send_client_node,
    notify_managers_node,
    update_session_node
])

# 3. Update connections
connections["Route by Event Type"] = {
    "main": [
        [
            {
                "node": "Parse WebApp Order & Match Distributor",
                "type": "main",
                "index": 0
            }
        ],
        [
            {
                "node": "Update Session Segment",
                "type": "main",
                "index": 0
            }
        ],
        [
            {
                "node": "Check Rate Limit",
                "type": "main",
                "index": 0
            }
        ],
        [
            {
                "node": "Send Segment Keyboard",
                "type": "main",
                "index": 0
            }
        ]
    ]
}

connections["Parse WebApp Order & Match Distributor"] = {
    "main": [
        [
            {
                "node": "Prepare Gotenberg Payload",
                "type": "main",
                "index": 0
            }
        ]
    ]
}

connections["Prepare Gotenberg Payload"] = {
    "main": [
        [
            {
                "node": "Generate PDF via Gotenberg (Order)",
                "type": "main",
                "index": 0
            }
        ]
    ]
}

connections["Generate PDF via Gotenberg (Order)"] = {
    "main": [
        [
            {
                "node": "Send PDF to Client",
                "type": "main",
                "index": 0
            },
            {
                "node": "Notify Managers Group (Order)",
                "type": "main",
                "index": 0
            }
        ]
    ]
}

connections["Notify Managers Group (Order)"] = {
    "main": [
        [
            {
                "node": "Update Order Session",
                "type": "main",
                "index": 0
            }
        ]
    ]
}

wf["nodes"] = nodes
wf["connections"] = connections

# Save back to file
with open(workflow_path, "w", encoding="utf-8") as f:
    json.dump([wf] if isinstance(workflows_data, list) else wf, f, indent=2, ensure_ascii=False)

print(f"Updated {workflow_path} successfully. Total nodes now: {len(nodes)}")

# Update PostgreSQL tables: workflow_entity and workflow_history
conn = psycopg2.connect(
    dbname='tork_bot_db',
    user='tork_admin',
    password='tork_db_pass_2026',
    host='localhost',
    port=5432
)
cur = conn.cursor()
cur.execute("""
    UPDATE workflow_entity 
    SET nodes = %s, connections = %s, "updatedAt" = NOW() 
    WHERE id = 'zF67bIQS8ypAMElC';
""", (json.dumps(nodes), json.dumps(connections)))

cur.execute("""
    UPDATE workflow_history 
    SET nodes = %s, connections = %s, "updatedAt" = NOW() 
    WHERE "workflowId" = 'zF67bIQS8ypAMElC';
""", (json.dumps(nodes), json.dumps(connections)))

conn.commit()
print("Updated workflow_entity AND workflow_history tables in PostgreSQL successfully.")
cur.close()
conn.close()
