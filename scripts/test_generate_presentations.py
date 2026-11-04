import os
import sys
import base64
import urllib.request
import urllib.parse
import uuid
import jinja2
import pypdf

# Add dashboard-api to sys.path so we can import tork_arguments
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dashboard-api")))
from app.services.tork_arguments import get_system_arguments

GOTENBERG_URL = os.getenv("GOTENBERG_URL", "http://localhost:3000/forms/chromium/convert/html")
TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../templates/presentation_template.html"))
ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../assets/images"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../generated_presentations"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

def image_to_base64_uri(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"

def render_pdf_with_gotenberg(html_content: str) -> bytes:
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    
    body = bytearray()
    
    def add_field(name, value):
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))
        
    def add_file(name, filename, content_bytes, content_type="text/html"):
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(content_bytes)
        body.extend(b"\r\n")

    # Add HTML file
    add_file("files", "index.html", html_content.encode("utf-8"), "text/html")
    
    # Gotenberg parameters
    add_field("marginTop", "0.39in")
    add_field("marginBottom", "0.31in")
    add_field("marginLeft", "0.47in")
    add_field("marginRight", "0.47in")
    add_field("preferCssPageSize", "true")
    add_field("printBackground", "true")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        GOTENBERG_URL,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("Starting Tork 5-System Presentation Generation Test")
    print("=" * 60)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tpl_str = f.read()

    env = jinja2.Environment(autoescape=True)
    template = env.from_string(tpl_str)

    test_cases = [
        {
            "id": 1,
            "system_code": "T8",
            "segment": "horeca",
            "sku": "680008",
            "filename": "Презентация_1_Tork_SmartOne_T8_Ресторан.pdf"
        },
        {
            "id": 2,
            "system_code": "H1",
            "segment": "office",
            "sku": "551000",
            "filename": "Презентация_2_Tork_Matic_H1_Офис_БЦ.pdf"
        },
        {
            "id": 3,
            "system_code": "H2",
            "segment": "medical",
            "sku": "552000",
            "filename": "Презентация_3_Tork_Xpress_H2_Клиника.pdf"
        },
        {
            "id": 4,
            "system_code": "S4",
            "segment": "horeca",
            "sku": "564500",
            "filename": "Презентация_4_Tork_FoamSoap_S4_Отель.pdf"
        },
        {
            "id": 5,
            "system_code": "B1",
            "segment": "general",
            "sku": "563000",
            "filename": "Презентация_5_Tork_Elevation_B1_Корзина.pdf"
        }
    ]

    all_passed = True

    for tc in test_cases:
        sys_info = get_system_arguments(tc["system_code"], tc["segment"])
        
        # Load sample product studio image
        sku_img_path = os.path.join(ASSETS_DIR, f"{tc['sku']}.png")
        after_img_uri = image_to_base64_uri(sku_img_path)

        context = {
            "system_name": sys_info["system_name"],
            "tagline": sys_info["tagline"],
            "dispenser_title": sys_info["dispenser_title"],
            "solution_summary": sys_info["solution_summary"],
            "arguments": sys_info["arguments"],
            "before_image_data_uri": "",  # Empty -> renders clean placeholder frame as requested
            "after_image_data_uri": after_img_uri,
            "is_contain_fit": True
        }

        rendered_html = template.render(**context)

        try:
            pdf_bytes = render_pdf_with_gotenberg(rendered_html)
            out_file = os.path.join(OUTPUT_DIR, tc["filename"])
            with open(out_file, "wb") as f:
                f.write(pdf_bytes)

            # Strict Page Count Validation
            reader = pypdf.PdfReader(out_file)
            page_count = len(reader.pages)
            file_size_kb = len(pdf_bytes) / 1024

            if page_count == 1:
                status = "✅ PASS (Strictly 1 Page)"
            else:
                status = f"❌ FAIL ({page_count} pages! Overflow detected)"
                all_passed = False

            print(f"[{tc['id']}/5] {tc['filename']}")
            print(f"     Status: {status} | Size: {file_size_kb:.1f} KB")

        except Exception as e:
            print(f"[{tc['id']}/5] ERROR in {tc['filename']}: {e}")
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 ALL 5 PRESENTATIONS GENERATED AND VALIDATED: 100% STRICTLY 1 PAGE!")
    else:
        print("⚠️ Some presentations failed page budget constraints.")
    print(f"Output directory: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
