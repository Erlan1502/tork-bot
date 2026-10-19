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

    # 1. Check or add Webhook Order Trigger node
    webhook_node = next((n for n in nodes if n["name"] == "Webhook Order Trigger"), None)
    if not webhook_node:
        webhook_node = {
            "parameters": {
                "httpMethod": "POST",
                "path": "web-app-order",
                "responseMode": "onReceived",
                "responseData": "allEntries",
                "options": {}
            },
            "id": "webhook-order-trigger",
            "name": "Webhook Order Trigger",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [-300, 750],
            "webhookId": "web-app-order"
        }
        nodes.append(webhook_node)
        print("Added Webhook Order Trigger node.")
    else:
        webhook_node["parameters"]["path"] = "web-app-order"
        webhook_node["webhookId"] = "web-app-order"
        print("Updated Webhook Order Trigger node.")

    # Connect Webhook Order Trigger to Parse WebApp Order & Match Distributor
    connections["Webhook Order Trigger"] = {
        "main": [
            [
                {
                    "node": "Parse WebApp Order & Match Distributor",
                    "type": "main",
                    "index": 0
                }
            ]
        ]
    }

    # 2. Update Parse WebApp Order & Match Distributor (SAFE against unexecuted Telegram Trigger)
    parse_node = next((n for n in nodes if n["name"] == "Parse WebApp Order & Match Distributor"), None)
    if parse_node:
        parse_node["parameters"]["jsCode"] = """let triggerJson = {};
try {
  triggerJson = $('Telegram Trigger').first()?.json || {};
} catch (e) {
  triggerJson = {};
}

const inputItem = $input.first()?.json || {};
const bodyJson = inputItem.body || inputItem;

const triggerData = triggerJson.message?.web_app_data?.data || inputItem.message?.web_app_data?.data || inputItem.web_app_data?.data;
let rawData = {};
try {
  rawData = typeof triggerData === 'string' ? JSON.parse(triggerData) : (triggerData || {});
} catch (e) {
  rawData = {};
}

if (!rawData.items) {
  if (bodyJson.items) {
    rawData = bodyJson;
  } else if (inputItem.items) {
    rawData = inputItem;
  }
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
const tgUserId = Number(rawData.chat_id || rawData.tg_user_id || tgUser.id || 0);
const tgUsername = rawData.tg_username || tgUser.username || '';
const clientName = rawData.client_name || tgUser.first_name || 'Представитель';

return [{
  json: {
    event: rawData.event || 'web_app_order',
    company_name: rawData.company_name || 'ТОО Рассвет',
    bin: rawData.bin || '',
    city: rawData.city || 'Астана',
    client_name: clientName,
    phone: rawData.phone || '',
    items: items,
    total_amount: totalAmount,
    total_amount_formatted: totalAmountFormatted,
    items_summary: itemsSummary,
    kp_number: kp_number,
    kp_date: kp_date,
    ...distributor,
    tg_user_id: tgUserId,
    tg_username: tgUsername
  }
}];"""
        print("Updated Parse WebApp Order & Match Distributor jsCode with try/catch.")

    # 3. Update Send PDF to Client
    send_pdf_node = next((n for n in nodes if n["name"] == "Send PDF to Client"), None)
    if send_pdf_node:
        send_pdf_node["parameters"]["chatId"] = "={{ $('Parse WebApp Order & Match Distributor').first().json.tg_user_id }}"
        print("Updated Send PDF to Client chatId expression.")

    # 4. Update Notify Managers Group (Order)
    notify_node = next((n for n in nodes if n["name"] == "Notify Managers Group (Order)"), None)
    if notify_node:
        caption_expr = (
            "={{ '🚨 Новая заявка из каталога Tork (Казахстан)\\n\\n"
            "🏢 Компания: ' + ($json.company_name || $('Parse WebApp Order & Match Distributor').first().json.company_name) + "
            "'\\n🔢 БИН/ИИН: ' + ($json.bin || $('Parse WebApp Order & Match Distributor').first().json.bin) + "
            "'\\n📍 Город: ' + ($json.city || $('Parse WebApp Order & Match Distributor').first().json.city) + "
            "'\\n👤 Контакт: ' + ($json.client_name || $('Parse WebApp Order & Match Distributor').first().json.client_name) + ' (' + ($json.phone || $('Parse WebApp Order & Match Distributor').first().json.phone) + ')' + "
            "'\\n💬 Telegram: @' + ($('Parse WebApp Order & Match Distributor').first().json.tg_username || 'нет') + "
            "'\\n\\n📦 Состав заказа:\\n' + ($json.items_summary || $('Parse WebApp Order & Match Distributor').first().json.items_summary) + "
            "'\\n\\n💰 Итого: ' + ($json.total_amount_formatted || $('Parse WebApp Order & Match Distributor').first().json.total_amount_formatted) + ' ₸"
            "\\n📄 Номер КП: ' + ($json.kp_number || $('Parse WebApp Order & Match Distributor').first().json.kp_number) }}"
        )
        notify_node["parameters"]["caption"] = caption_expr
        if "additionalFields" in notify_node["parameters"]:
            notify_node["parameters"]["additionalFields"]["caption"] = caption_expr
        print("Updated Notify Managers Group (Order) caption.")

    # 5. Update Update Order Session (Upsert instead of simple UPDATE)
    update_session_node = next((n for n in nodes if n["name"] == "Update Order Session"), None)
    if update_session_node:
        upsert_query = (
            "INSERT INTO user_sessions_leads (tg_user_id, tg_username, client_name, company_name, phone, current_step, selected_bundle, distributor_id, updated_at) "
            "VALUES ("
            "{{ $('Parse WebApp Order & Match Distributor').first().json.tg_user_id || 0 }}, "
            "'{{ ($('Parse WebApp Order & Match Distributor').first().json.tg_username || '').replace(/'/g, \"''\") }}', "
            "'{{ ($('Parse WebApp Order & Match Distributor').first().json.client_name || '').replace(/'/g, \"''\") }}', "
            "'{{ ($('Parse WebApp Order & Match Distributor').first().json.company_name || '').replace(/'/g, \"''\") }}', "
            "'{{ ($('Parse WebApp Order & Match Distributor').first().json.phone || '').replace(/'/g, \"''\") }}', "
            "'ORDER_COMPLETED', "
            "'{{ JSON.stringify($('Parse WebApp Order & Match Distributor').first().json.items || []).replace(/'/g, \"''\") }}'::jsonb, "
            "{{ $('Parse WebApp Order & Match Distributor').first().json.distributor_id || 1 }}, "
            "NOW()"
            ") "
            "ON CONFLICT (tg_user_id) DO UPDATE SET "
            "company_name = EXCLUDED.company_name, "
            "phone = EXCLUDED.phone, "
            "client_name = EXCLUDED.client_name, "
            "current_step = 'ORDER_COMPLETED', "
            "selected_bundle = EXCLUDED.selected_bundle, "
            "distributor_id = EXCLUDED.distributor_id, "
            "updated_at = NOW();"
        )
        update_session_node["parameters"]["query"] = upsert_query
        print("Updated Update Order Session query.")

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
