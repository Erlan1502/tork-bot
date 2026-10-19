import urllib.request
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
template_file = root_dir / "templates" / "kp_catalog_template.html"

with open(template_file, "r", encoding="utf-8") as f:
    html = f.read()

replacements = {
    "distributor_name": 'ТОО "Tork Kazakhstan Distribution Astana"',
    "distributor_bin": "210540032111",
    "distributor_city": "г. Астана",
    "distributor_address": 'г. Астана, район Есиль, ул. Достык, 18, БЦ "Москва", офис 704',
    "distributor_phone": "+7 (7172) 79-55-01",
    "distributor_email": "astana@tork-distrib.kz",
    "kp_number": "TKZ-123456",
    "kp_date": "19.10.2026",
    "client_name": "ТОО Ксюша (контакт: Ерлан Кубесов)",
    "bin": "123456789012",
    "city": "Астана",
    "phone": "+7 (775) 930-38-21",
    "table_rows_html": '<tr><td class="text-center">1</td><td><strong>100278</strong></td><td>Tork листовые полотенца Singlefold-V</td><td class="text-center"><span class="badge">H3</span></td><td class="text-center">1</td><td class="text-right">3 180 ₸</td><td class="text-right"><strong>3 180 ₸</strong></td></tr>',
    "total_amount_formatted": "3 180"
}

for k, v in replacements.items():
    html = html.replace("{{ " + k + " }}", v).replace("{{" + k + "}}", v)

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="files"; filename="index.html"\r\n'
    f"Content-Type: text/html\r\n\r\n"
    f"{html}\r\n"
    f"--{boundary}--\r\n"
).encode("utf-8")

req = urllib.request.Request(
    "http://localhost:3000/forms/chromium/convert/html",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
)

resp = urllib.request.urlopen(req)
pdf_data = resp.read()
output_pdf = root_dir / "scripts" / "test_catalog_kp.pdf"
with open(output_pdf, "wb") as f:
    f.write(pdf_data)

print(f"Generated PDF successfully! Size: {len(pdf_data)} bytes. Saved to {output_pdf}")
