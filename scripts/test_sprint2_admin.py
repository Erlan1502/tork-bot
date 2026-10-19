import sys
import urllib.request
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://localhost:8088"

def make_request(url, method="GET", data=None, token=None, headers=None):
    if headers is None:
        headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif isinstance(data, (bytes, bytearray)):
            body = data
        elif isinstance(data, str):
            body = data.encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data_bytes = resp.read()
            if "application/json" in content_type:
                return resp.status, resp.headers, json.loads(data_bytes.decode("utf-8"))
            return resp.status, resp.headers, data_bytes
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(error_body)
        except Exception:
            parsed = error_body
        return e.code, e.headers, parsed

def test_sprint2():
    print("=================================================================")
    print("▶ STARTING SPRINT 2 END-TO-END VALIDATION")
    print("=================================================================")

    # 1. Test Static Admin SPA
    print("\n[1] Testing Static SPA Serving at /admin/")
    status, headers, content = make_request(f"{BASE_URL}/admin/")
    assert status == 200, f"Expected 200 from /admin/, got {status}"
    html_text = content.decode("utf-8")
    assert "Tork" in html_text or "TORK" in html_text, "Tork not found in HTML"
    assert "app.js" in html_text, "app.js not referenced"
    print("  ✓ /admin/ serves index.html with 200 OK")

    # 2. Test Vendor Admin Login
    print("\n[2] Testing Vendor Admin Login (admin@tork.kz)")
    status, _, data = make_request(
        f"{BASE_URL}/api/admin/auth/login",
        method="POST",
        data={"email": "admin@tork.kz", "password": "TorkKZ2026!"}
    )
    assert status == 200, f"Login failed: {data}"
    vendor_token = data["access_token"]
    vendor_user = data["user"]
    assert vendor_user["role"] == "vendor_admin"
    print(f"  ✓ Logged in as: {vendor_user['full_name']} (Role: {vendor_user['role']})")

    # 3. Test Orders List as Vendor Admin
    print("\n[3] Testing Vendor Admin Orders Visibility")
    status, _, orders_data = make_request(
        f"{BASE_URL}/api/admin/orders",
        token=vendor_token
    )
    assert status == 200
    all_orders = orders_data["items"]
    print(f"  ✓ Vendor sees {len(all_orders)} orders (Total in DB: {orders_data['total']})")
    dist_ids = {o["distributor_id"] for o in all_orders if o["distributor_id"] is not None}
    print(f"  ✓ Distributor IDs present in vendor view: {sorted(list(dist_ids))}")

    # 4. Test Search filter
    print("\n[4] Testing Search Query filter")
    import urllib.parse
    search_q = urllib.parse.quote("Астана")
    status, _, search_data = make_request(
        f"{BASE_URL}/api/admin/orders?search={search_q}",
        token=vendor_token
    )
    assert status == 200
    print(f"  ✓ Search 'Астана' returned {len(search_data['items'])} matching orders")

    # 5. Test Status Update & Notes (Order #82)
    print("\n[5] Testing Status Update & Manager Notes on Order #82")
    status, _, update_data = make_request(
        f"{BASE_URL}/api/admin/orders/82/status",
        method="PATCH",
        token=vendor_token,
        data={"order_status": "TEST_DRIVE", "manager_notes": "Клиент согласовал бесплатный тест-драйв на 14 дней"}
    )
    assert status == 200, f"Update failed: {update_data}"
    assert update_data["order_status"] == "TEST_DRIVE"
    assert "бесплатный тест-драйв" in update_data["manager_notes"]
    print(f"  ✓ Order #82 updated status to TEST_DRIVE and saved note")

    # 6. Test PDF Download via Gotenberg on Order #82
    print("\n[6] Testing PDF Generation & Download (GET /api/admin/orders/82/pdf)")
    status, headers, pdf_bytes = make_request(
        f"{BASE_URL}/api/admin/orders/82/pdf",
        token=vendor_token
    )
    assert status == 200, f"PDF generation failed: status {status}, response: {pdf_bytes}"
    assert headers.get("Content-Type") == "application/pdf", f"Unexpected content-type: {headers.get('Content-Type')}"
    cd = headers.get("Content-Disposition", "")
    assert "attachment" in cd and ".pdf" in cd, f"Unexpected content-disposition: {cd}"
    assert pdf_bytes.startswith(b"%PDF-"), "Generated file is not a valid PDF"
    print(f"  ✓ Received valid PDF! Size: {len(pdf_bytes):,} bytes, Filename header: {cd}")

    # 7. Test Distributor Manager Login (astana@tork.kz)
    print("\n[7] Testing Distributor Manager Login (astana@tork.kz)")
    status, _, data = make_request(
        f"{BASE_URL}/api/admin/auth/login",
        method="POST",
        data={"email": "astana@tork.kz", "password": "TorkKZ2026!"}
    )
    assert status == 200
    astana_token = data["access_token"]
    astana_user = data["user"]
    assert astana_user["role"] == "distributor_manager"
    assert astana_user["distributor_id"] == 1
    print(f"  ✓ Logged in as: {astana_user['full_name']} (Distributor ID: {astana_user['distributor_id']})")

    # 8. Test Data Isolation for Astana Manager
    print("\n[8] Testing RBAC Data Isolation for Astana Manager")
    status, _, astana_orders = make_request(
        f"{BASE_URL}/api/admin/orders",
        token=astana_token
    )
    assert status == 200
    for o in astana_orders["items"]:
        assert o["distributor_id"] == 1, f"Data isolation breach! Order #{o['id']} has distributor_id {o['distributor_id']}"
    print(f"  ✓ Astana manager sees strictly distributor_id=1 ({len(astana_orders['items'])} orders)")

    # 9. Test Access Control: Astana manager trying to access Order #83 (Almaty)
    print("\n[9] Testing RBAC: Astana manager accessing Order #83 (Almaty)")
    status, _, err_detail = make_request(
        f"{BASE_URL}/api/admin/orders/83",
        token=astana_token
    )
    assert status == 403, f"Expected 403 Forbidden, got {status}: {err_detail}"
    print(f"  ✓ Blocked with 403 Forbidden: {err_detail.get('detail')}")

    # 10. Test Access Control: Astana manager trying to download PDF of Order #83 (Almaty)
    print("\n[10] Testing RBAC: Astana manager downloading PDF of Order #83 (Almaty)")
    status, _, err_detail = make_request(
        f"{BASE_URL}/api/admin/orders/83/pdf",
        token=astana_token
    )
    assert status == 403, f"Expected 403 Forbidden, got {status}: {err_detail}"
    print(f"  ✓ Blocked with 403 Forbidden: {err_detail.get('detail')}")

    # 11. Astana manager downloading their own Order #82 PDF
    print("\n[11] Testing Astana manager downloading PDF of their own Order #82")
    status, headers, pdf_bytes = make_request(
        f"{BASE_URL}/api/admin/orders/82/pdf",
        token=astana_token
    )
    assert status == 200
    assert pdf_bytes.startswith(b"%PDF-")
    print(f"  ✓ Astana manager successfully downloaded own order PDF ({len(pdf_bytes):,} bytes)")

    print("\n=================================================================")
    print("✅ ALL SPRINT 2 SPECIFICATIONS & DOD CRITERIA PASSED!")
    print("=================================================================")

if __name__ == "__main__":
    test_sprint2()
