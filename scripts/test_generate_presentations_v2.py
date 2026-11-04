import os
import sys
import base64
import urllib.request
import uuid
import jinja2
import pypdf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dashboard-api")))
from app.services.tork_arguments import get_system_arguments

GOTENBERG_URL = os.getenv("GOTENBERG_URL", "http://localhost:3000/forms/chromium/convert/html")
GOTENBERG_SCREENSHOT_URL = os.getenv("GOTENBERG_SCREENSHOT_URL", "http://localhost:3000/forms/chromium/screenshot/html")
TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../templates/presentation_template.html"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../generated_presentations"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

def image_to_base64_uri(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image not found: {file_path}")
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"

def render_pdf(html_content: str) -> bytes:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="files"; filename="index.html"\r\nContent-Type: text/html\r\n\r\n')
    body.extend(html_content.encode("utf-8"))
    body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="preferCssPageSize"\r\n\r\ntrue\r\n')

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="printBackground"\r\n\r\ntrue\r\n')

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        GOTENBERG_URL,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def render_screenshot(html_content: str) -> bytes:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="files"; filename="index.html"\r\nContent-Type: text/html\r\n\r\n')
    body.extend(html_content.encode("utf-8"))
    body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="width"\r\n\r\n794\r\n')

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="height"\r\n\r\n1123\r\n')

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        GOTENBERG_SCREENSHOT_URL,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("Generating 3 Real-Case Presentations (Harmonious Spacing & Real Photos)")
    print("=" * 60)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tpl_str = f.read()

    template = jinja2.Environment(autoescape=True).from_string(tpl_str)

    cases = [
        {
            "id": 1,
            "title": "Пример 1: Tork SmartOne T8 (Ресторан / HoReCa)",
            "system_code": "T8",
            "segment": "horeca",
            "before_path": os.path.abspath("assets/sample_fittings/pres_sample_0.png"),
            "after_path": os.path.abspath("assets/sample_fittings/pres_sample_1.png"),
            "pdf_name": "Презентация_V2_1_Tork_SmartOne_T8_Ресторан.pdf",
            "png_name": "preview_v2_1_T8_SmartOne.png"
        },
        {
            "id": 2,
            "title": "Пример 2: Tork Matic H1 (Офис / Бизнес-центр)",
            "system_code": "H1",
            "segment": "office",
            "before_path": os.path.abspath("assets/sample_fittings/manana_2.png"),
            "after_path": os.path.abspath("gemini_test_fitting.jpg"),
            "pdf_name": "Презентация_V2_2_Tork_Matic_H1_Офис.pdf",
            "png_name": "preview_v2_2_H1_Matic.png"
        },
        {
            "id": 3,
            "title": "Пример 3: Tork S4 Мыло-пена (Клиника / Медцентр)",
            "system_code": "S4",
            "segment": "medical",
            "before_path": os.path.abspath("assets/sample_fittings/manana_0.png"),
            "after_path": os.path.abspath("gemini_multi_kit_fitting.jpg"),
            "pdf_name": "Презентация_V2_3_Tork_FoamSoap_S4_Клиника.pdf",
            "png_name": "preview_v2_3_S4_FoamSoap.png"
        }
    ]

    for c in cases:
        sys_info = get_system_arguments(c["system_code"], c["segment"])
        
        before_uri = image_to_base64_uri(c["before_path"])
        after_uri = image_to_base64_uri(c["after_path"])

        context = {
            "system_name": sys_info["system_name"],
            "tagline": sys_info["tagline"],
            "solution_summary": sys_info["solution_summary"],
            "arguments": sys_info["arguments"],
            "before_image_data_uri": before_uri,
            "after_image_data_uri": after_uri
        }

        html = template.render(**context)

        # 1. Render PDF
        pdf_bytes = render_pdf(html)
        pdf_path = os.path.join(OUTPUT_DIR, c["pdf_name"])
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # 2. Render Screenshot
        png_bytes = render_screenshot(html)
        png_path = os.path.join(OUTPUT_DIR, c["png_name"])
        with open(png_path, "wb") as f:
            f.write(png_bytes)

        # Validate Page Count
        reader = pypdf.PdfReader(pdf_path)
        pages = len(reader.pages)
        status = "✅ PASS (Strictly 1 Page)" if pages == 1 else f"❌ FAIL ({pages} pages)"

        print(f"[{c['id']}/3] {c['title']}")
        print(f"      PDF: {c['pdf_name']} -> {status} ({len(pdf_bytes)/1024:.1f} KB)")
        print(f"      PNG: {c['png_name']} ({len(png_bytes)/1024:.1f} KB)")

    print("=" * 60)
    print("Done generating updated presentation examples.")

if __name__ == "__main__":
    main()

