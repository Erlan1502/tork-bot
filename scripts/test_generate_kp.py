import os
import sys
import uuid
import urllib.request
import jinja2
import pypdf

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../templates/kp_kz_template.html"))
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../generated_presentations"))
    os.makedirs(output_dir, exist_ok=True)

    with open(template_path, "r", encoding="utf-8") as f:
        tpl_str = f.read()

    template = jinja2.Environment().from_string(tpl_str)

    context = {
        "client_name": "ТОО «Grand Hotel Astana»",
        "client_facility": "Гостиничный комплекс, 5 этажей, 42 санузла",
        "client_city": "г. Астана",
        "kp_date": "05 ноября 2026 г.",
        "manager_name": "Ерлан Садыков",
        "manager_phone": "+7 (777) 123-45-67",
        "manager_tg": "@erlan_tork_kz",
        "total_amount_formatted": "3 450 000",
        "prepayment_amount_formatted": "1 725 000",
        "postpayment_amount_formatted": "1 725 000",
        "total_dispensers_count": "56",
        "dispenser_items": [
            {
                "sku": "551000",
                "name": "Matic® диспенсер для полотенец в рулонах",
                "color": "Белый Elevation",
                "dimensions": "37,2 × 33,7 × 20,3 см",
                "system_code": "H1",
                "count": 16,
                "price_formatted": "85 000 ₸",
                "total_formatted": "1 360 000 ₸"
            },
            {
                "sku": "680008",
                "name": "SmartOne® диспенсер для туалетной бумаги",
                "color": "Черный матовый Elevation",
                "dimensions": "26,9 × 26,9 × 15,6 см",
                "system_code": "T8",
                "count": 20,
                "price_formatted": "42 000 ₸",
                "total_formatted": "840 000 ₸"
            },
            {
                "sku": "564500",
                "name": "Дозатор для мыла-пены S4",
                "color": "Белый Elevation",
                "dimensions": "29 × 11,2 × 9,9 см",
                "system_code": "S4",
                "count": 12,
                "price_formatted": "35 000 ₸",
                "total_formatted": "420 000 ₸"
            },
            {
                "sku": "563000",
                "name": "Корзина для мусора 50 л со скрытым мешком B1",
                "color": "Белый Elevation",
                "dimensions": "62,9 × 38,9 × 18,9 см",
                "system_code": "B1",
                "count": 8,
                "price_formatted": "55 000 ₸",
                "total_formatted": "440 000 ₸"
            }
        ],
        "refill_items": [
            {
                "sku": "290016",
                "name": "Matic® мягкие рулонные полотенца Premium",
                "quality": "2 слоя, тиснение «лист», ультрамягкие",
                "description": "100 м в рулоне",
                "system_code": "H1",
                "packaging": "6 рул. / кор.",
                "price_formatted": "18 500 ₸"
            },
            {
                "sku": "472242",
                "name": "SmartOne® туалетная бумага в рулонах Advanced",
                "quality": "2 слоя, моментальное растворение 8 сек",
                "description": "207 м, 1150 листов",
                "system_code": "T8",
                "packaging": "6 рул. / кор.",
                "price_formatted": "12 800 ₸"
            },
            {
                "sku": "520501",
                "name": "Мыло-пена мягкое Premium 1 л",
                "quality": "2 500 доз, гипоаллергенное",
                "description": "Герметичный одноразовый картридж",
                "system_code": "S4",
                "packaging": "6 флак. / кор.",
                "price_formatted": "8 900 ₸"
            }
        ]
    }

    html = template.render(**context)

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="files"; filename="index.html"\r\nContent-Type: text/html\r\n\r\n')
    body.extend(html.encode("utf-8"))
    body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="preferCssPageSize"\r\n\r\ntrue\r\n')

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="printBackground"\r\n\r\ntrue\r\n')

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "http://localhost:3000/forms/chromium/convert/html",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        pdf_bytes = resp.read()

    out_file = os.path.join(output_dir, "Образец_КП_Tork_Казахстан_Grand_Hotel.pdf")
    with open(out_file, "wb") as f:
        f.write(pdf_bytes)

    reader = pypdf.PdfReader(out_file)
    print(f"✅ Generated Commercial Proposal: {out_file}")
    print(f"   Pages: {len(reader.pages)} | Size: {len(pdf_bytes)/1024:.1f} KB")

if __name__ == "__main__":
    main()

