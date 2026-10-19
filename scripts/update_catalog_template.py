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

    prepare_order_node = next((n for n in nodes if n["name"] == "Prepare Gotenberg Payload"), None)
    if not prepare_order_node:
        raise ValueError("Could not find 'Prepare Gotenberg Payload' node")

    prepare_order_node["parameters"]["jsCode"] = """const fs = require('fs');

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

// Use dedicated catalog template WITHOUT the visualization block
const templatePath = '/data/templates/kp_catalog_template.html';
let htmlContent = '';
try {
  htmlContent = fs.readFileSync(templatePath, 'utf8');
} catch (e) {
  try {
    htmlContent = fs.readFileSync('/data/templates/kp_template.html', 'utf8');
  } catch (err) {
    htmlContent = '<html><body><h1>Коммерческое предложение Tork</h1></body></html>';
  }
}

const clientNameFormatted = rawData.client_name 
  ? `${rawData.company_name} (контакт: ${rawData.client_name})` 
  : rawData.company_name;

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
  bin: rawData.bin || '—',
  city: rawData.city || 'Казахстан',
  phone: rawData.phone || '—',
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

    print("Updated 'Prepare Gotenberg Payload' jsCode to use kp_catalog_template.html")

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
