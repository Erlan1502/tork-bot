import os
import sys
import uuid
import urllib.request
import base64
import jinja2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dashboard-api")))
from app.services.tork_arguments import get_system_arguments

def image_to_base64_uri(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"

def main():
    template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../templates/presentation_template.html"))
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../generated_presentations"))
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../assets/images"))
    
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    template = jinja2.Environment().from_string(html)
    
    test_cases = [
        {"id": 1, "code": "T8", "seg": "horeca", "sku": "680008", "name": "preview_1_T8_SmartOne.png"},
        {"id": 2, "code": "H1", "seg": "office", "sku": "551000", "name": "preview_2_H1_Matic.png"},
        {"id": 3, "code": "H2", "seg": "medical", "sku": "552000", "name": "preview_3_H2_Xpress.png"},
        {"id": 4, "code": "S4", "seg": "horeca", "sku": "564500", "name": "preview_4_S4_FoamSoap.png"},
        {"id": 5, "code": "B1", "seg": "general", "sku": "563000", "name": "preview_5_B1_WasteBin.png"},
    ]

    for tc in test_cases:
        sys_info = get_system_arguments(tc["code"], tc["seg"])
        sku_img_path = os.path.join(assets_dir, f"{tc['sku']}.png")
        after_img_uri = image_to_base64_uri(sku_img_path)

        rendered = template.render(
            system_name=sys_info["system_name"],
            tagline=sys_info["tagline"],
            dispenser_title=sys_info["dispenser_title"],
            solution_summary=sys_info["solution_summary"],
            arguments=sys_info["arguments"],
            before_image_data_uri="",
            after_image_data_uri=after_img_uri,
            is_contain_fit=True
        )

        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="files"; filename="index.html"\r\nContent-Type: text/html\r\n\r\n')
        body.extend(rendered.encode("utf-8"))
        body.extend(b"\r\n")

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="width"\r\n\r\n794\r\n')

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="height"\r\n\r\n1123\r\n')

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(
            "http://localhost:3000/forms/chromium/screenshot/html",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            img_bytes = resp.read()

        preview_path = os.path.join(output_dir, tc["name"])
        with open(preview_path, "wb") as f:
            f.write(img_bytes)
        print(f"[{tc['id']}/5] Saved preview screenshot: {preview_path}")

if __name__ == "__main__":
    main()
