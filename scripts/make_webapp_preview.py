import urllib.request
import uuid
import os

def main():
    url = "http://cdn/app/index.html"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="url"\r\n\r\n')
    body.extend(url.encode("utf-8"))
    body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="width"\r\n\r\n390\r\n')

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="height"\r\n\r\n844\r\n')

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "http://localhost:3000/forms/chromium/screenshot/url",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        img = resp.read()

    out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../generated_presentations/preview_webapp_mobile.png"))
    with open(out_file, "wb") as f:
        f.write(img)
    print(f"Saved mobile screenshot: {out_file} ({len(img)/1024:.1f} KB)")

if __name__ == "__main__":
    main()

