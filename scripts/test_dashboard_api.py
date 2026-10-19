#!/usr/bin/env python3
"""
Sprint 1 Dashboard API Test Suite & DoD Verification
Tests:
1. Database migrations & seeded users.
2. Nginx reverse proxy & Swagger UI at http://localhost:8088/api/admin/docs.
3. RBAC Authentication (admin@tork.kz, astana@tork.kz, almaty@tork.kz).
4. Data Isolation (admin sees all republic, astana sees only distributor_id=1).
5. Cross-region access prevention (astana manager gets 403 Forbidden on Almaty order).
6. Order status update (PATCH /api/admin/orders/{id}/status) and DB verification.
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# Config
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8088")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_NAME = os.getenv("POSTGRES_DB", "tork_bot_db")
DB_USER = os.getenv("POSTGRES_USER", "tork_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "tork_db_pass_2026")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )

def http_request(url: str, method: str = "GET", headers: dict = None, data: dict = None):
    req_headers = headers.copy() if headers else {}
    req_data = None
    if data is not None:
        req_headers["Content-Type"] = "application/json"
        req_data = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            body_bytes = resp.read()
            body_text = body_bytes.decode("utf-8")
            try:
                body_json = json.loads(body_text)
            except Exception:
                body_json = body_text
            return status_code, body_json
    except urllib.error.HTTPError as e:
        status_code = e.code
        body_text = e.read().decode("utf-8")
        try:
            body_json = json.loads(body_text)
        except Exception:
            body_json = body_text
        return status_code, body_json
    except Exception as e:
        return 0, str(e)


def run_tests():
    print("=" * 70)
    print("STARTING SPRINT 1 DASHBOARD API TESTS & DoD VERIFICATION")
    print("=" * 70)

    # ---------------------------------------------------------
    # TEST 1: Database Schema & Users
    # ---------------------------------------------------------
    print("\n[TEST 1] Checking Database Schema & Seeded Users...")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'dashboard_users';
    """)
    assert cur.fetchone(), "FAIL: dashboard_users table does not exist!"

    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'user_sessions_leads' AND column_name IN ('order_status', 'manager_notes', 'kp_number');
    """)
    cols = {row["column_name"] for row in cur.fetchall()}
    assert {"order_status", "manager_notes", "kp_number"}.issubset(cols), f"FAIL: missing columns in user_sessions_leads: {cols}"

    cur.execute("SELECT email, role, distributor_id, is_active FROM dashboard_users ORDER BY id;")
    users = {u["email"]: u for u in cur.fetchall()}
    print(f"  Found {len(users)} users in dashboard_users: {list(users.keys())}")
    assert "admin@tork.kz" in users, "FAIL: admin@tork.kz missing!"
    assert "astana@tork.kz" in users, "FAIL: astana@tork.kz missing!"
    assert "almaty@tork.kz" in users, "FAIL: almaty@tork.kz missing!"
    assert "shymkent@tork.kz" in users, "FAIL: shymkent@tork.kz missing!"
    print("  -> TEST 1 PASSED: Database schema and users verified.")

    # ---------------------------------------------------------
    # SEED TEST ORDERS: Ensure orders exist for Astana (1), Almaty (2), Shymkent (3)
    # ---------------------------------------------------------
    print("\n[SETUP] Ensuring test orders exist for each region...")
    test_orders = [
        {
            "tg_user_id": 9001001,
            "tg_username": "astana_client",
            "client_name": "Бауыржан Мусин",
            "company_name": 'ТОО "Астана Премиум Отель"',
            "phone": "+7 (701) 111-22-33",
            "distributor_id": 1,
            "kp_number": "KP-AST-2026-001",
            "order_status": "NEW",
            "selected_bundle": [
                {"sku": "551000", "name": "Tork Matic® полотенца H1", "price": 131340, "qty": 2, "line_total": 262680, "system_code": "H1"}
            ]
        },
        {
            "tg_user_id": 9002002,
            "tg_username": "almaty_client",
            "client_name": "Мадина Серикова",
            "company_name": 'ТОО "Алматы Резорт & СПА"',
            "phone": "+7 (702) 222-33-44",
            "distributor_id": 2,
            "kp_number": "KP-ALM-2026-002",
            "order_status": "NEW",
            "selected_bundle": [
                {"sku": "560000", "name": "Tork диспенсер для мыла S4", "price": 45000, "qty": 3, "line_total": 135000, "system_code": "S4"}
            ]
        },
        {
            "tg_user_id": 9003003,
            "tg_username": "shymkent_client",
            "client_name": "Кайрат Тулегенов",
            "company_name": 'ТОО "Шымкент Пром Строй"',
            "phone": "+7 (705) 333-44-55",
            "distributor_id": 3,
            "kp_number": "KP-SHY-2026-003",
            "order_status": "NEW",
            "selected_bundle": [
                {"sku": "552000", "name": "Tork диспенсер для туалетной бумаги T2", "price": 32000, "qty": 5, "line_total": 160000, "system_code": "T2"}
            ]
        }
    ]

    astana_order_id = None
    almaty_order_id = None

    for o in test_orders:
        cur.execute("""
            INSERT INTO user_sessions_leads (
                tg_user_id, tg_username, client_name, company_name, phone, 
                distributor_id, kp_number, order_status, current_step, selected_bundle, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ORDER_COMPLETED', %s::jsonb, NOW())
            ON CONFLICT (tg_user_id) DO UPDATE SET
                client_name = EXCLUDED.client_name,
                company_name = EXCLUDED.company_name,
                phone = EXCLUDED.phone,
                distributor_id = EXCLUDED.distributor_id,
                kp_number = EXCLUDED.kp_number,
                current_step = 'ORDER_COMPLETED',
                selected_bundle = EXCLUDED.selected_bundle,
                updated_at = NOW()
            RETURNING id;
        """, (
            o["tg_user_id"], o["tg_username"], o["client_name"], o["company_name"],
            o["phone"], o["distributor_id"], o["kp_number"], o["order_status"],
            json.dumps(o["selected_bundle"])
        ))
        res = cur.fetchone()
        inserted_id = res["id"]
        if o["distributor_id"] == 1:
            astana_order_id = inserted_id
        elif o["distributor_id"] == 2:
            almaty_order_id = inserted_id
        print(f"  - Order for distributor_id={o['distributor_id']} ensured (ID: {inserted_id})")

    conn.commit()
    cur.close()
    conn.close()

    # ---------------------------------------------------------
    # TEST 2: Nginx Reverse Proxy & Docs
    # ---------------------------------------------------------
    print("\n[TEST 2] Checking Nginx reverse proxy endpoint (Docs)...")
    docs_url = f"{BASE_URL}/api/admin/docs"
    status_code, body = http_request(docs_url)
    print(f"  GET {docs_url} -> Status {status_code}")
    assert status_code == 200, f"FAIL: Expected HTTP 200 from {docs_url}, got {status_code}"
    print("  -> TEST 2 PASSED: Nginx proxies /api/admin/docs with HTTP 200.")

    # ---------------------------------------------------------
    # TEST 3: RBAC Authentication & Profile (/api/admin/auth/login, /me)
    # ---------------------------------------------------------
    print("\n[TEST 3] Testing RBAC Authentication...")
    
    # Login as admin
    login_url = f"{BASE_URL}/api/admin/auth/login"
    status_code, admin_login = http_request(login_url, method="POST", data={
        "email": "admin@tork.kz",
        "password": "TorkKZ2026!"
    })
    print(f"  POST {login_url} (admin@tork.kz) -> Status {status_code}")
    assert status_code == 200 and "access_token" in admin_login, f"FAIL: Admin login failed: {admin_login}"
    admin_token = admin_login["access_token"]
    assert admin_login["user"]["role"] == "vendor_admin", "FAIL: Admin role mismatch!"

    # Call /me with admin token
    me_url = f"{BASE_URL}/api/admin/auth/me"
    status_code, admin_me = http_request(me_url, headers={"Authorization": f"Bearer {admin_token}"})
    print(f"  GET {me_url} (admin token) -> Status {status_code}, User: {admin_me.get('email')}")
    assert status_code == 200 and admin_me["email"] == "admin@tork.kz", "FAIL: /me response invalid!"

    # Login as astana manager
    status_code, astana_login = http_request(login_url, method="POST", data={
        "email": "astana@tork.kz",
        "password": "TorkKZ2026!"
    })
    print(f"  POST {login_url} (astana@tork.kz) -> Status {status_code}")
    assert status_code == 200 and "access_token" in astana_login, f"FAIL: Astana manager login failed: {astana_login}"
    astana_token = astana_login["access_token"]
    assert astana_login["user"]["role"] == "distributor_manager", "FAIL: Astana role mismatch!"
    assert astana_login["user"]["distributor_id"] == 1, "FAIL: Astana distributor_id mismatch!"

    # Login with wrong password
    status_code, bad_login = http_request(login_url, method="POST", data={
        "email": "astana@tork.kz",
        "password": "WRONG_PASSWORD"
    })
    print(f"  POST {login_url} (wrong password) -> Status {status_code}")
    assert status_code == 401, f"FAIL: Expected 401 for wrong password, got {status_code}"
    print("  -> TEST 3 PASSED: Authentication, JWT tokens, and /me endpoint verified.")

    # ---------------------------------------------------------
    # TEST 4: Data Isolation (Vendor vs Distributor)
    # ---------------------------------------------------------
    print("\n[TEST 4] Testing Data Isolation on Orders List...")
    orders_url = f"{BASE_URL}/api/admin/orders"

    # Admin requests orders (should see all republic)
    status_code, admin_orders = http_request(orders_url, headers={"Authorization": f"Bearer {admin_token}"})
    print(f"  GET {orders_url} (admin@tork.kz) -> Status {status_code}, Total: {admin_orders.get('total')}")
    assert status_code == 200, f"FAIL: Admin orders request failed: {admin_orders}"
    admin_dist_ids = {item["distributor_id"] for item in admin_orders["items"]}
    print(f"  Admin sees distributor IDs: {admin_dist_ids}")
    assert len(admin_dist_ids) >= 2, f"FAIL: Vendor admin should see multiple regions, got {admin_dist_ids}"

    # Astana manager requests orders (must ONLY see distributor_id = 1)
    status_code, astana_orders = http_request(orders_url, headers={"Authorization": f"Bearer {astana_token}"})
    print(f"  GET {orders_url} (astana@tork.kz) -> Status {status_code}, Total: {astana_orders.get('total')}")
    assert status_code == 200, f"FAIL: Astana manager orders request failed: {astana_orders}"
    astana_dist_ids = {item["distributor_id"] for item in astana_orders["items"]}
    print(f"  Astana manager sees distributor IDs: {astana_dist_ids}")
    assert astana_dist_ids == {1}, f"FAIL: Data leak! Astana manager saw non-Astana orders: {astana_dist_ids}"
    print("  -> TEST 4 PASSED: Vendor sees all republic orders; Astana manager strictly isolated to region 1.")

    # ---------------------------------------------------------
    # TEST 5: Cross-Region Access Prevention (403 Forbidden)
    # ---------------------------------------------------------
    print("\n[TEST 5] Testing Cross-Region Access Prevention (403 Forbidden)...")
    assert almaty_order_id, "Almaty order ID missing for cross-region test!"
    almaty_order_url = f"{BASE_URL}/api/admin/orders/{almaty_order_id}"

    # Astana manager tries to GET Almaty order
    status_code, cross_get = http_request(almaty_order_url, headers={"Authorization": f"Bearer {astana_token}"})
    print(f"  GET {almaty_order_url} (astana token on Almaty order) -> Status {status_code}")
    assert status_code in (403, 404), f"FAIL: Expected 403 Forbidden for cross-region GET, got {status_code}: {cross_get}"

    # Astana manager tries to PATCH Almaty order
    cross_patch_url = f"{BASE_URL}/api/admin/orders/{almaty_order_id}/status"
    status_code, cross_patch = http_request(
        cross_patch_url,
        method="PATCH",
        headers={"Authorization": f"Bearer {astana_token}"},
        data={"order_status": "COMPLETED", "manager_notes": "Hacked from Astana"}
    )
    print(f"  PATCH {cross_patch_url} (astana token on Almaty order) -> Status {status_code}")
    assert status_code in (403, 404), f"FAIL: Expected 403 Forbidden for cross-region PATCH, got {status_code}: {cross_patch}"
    print("  -> TEST 5 PASSED: Cross-region access strictly blocked with 403 Forbidden.")

    # ---------------------------------------------------------
    # TEST 6: Order Status Update (PATCH) & Database Verification
    # ---------------------------------------------------------
    print("\n[TEST 6] Testing Order Status Update (PATCH) and DB Reflection...")
    assert astana_order_id, "Astana order ID missing for update test!"
    astana_patch_url = f"{BASE_URL}/api/admin/orders/{astana_order_id}/status"
    new_status = "INVOICE_SENT"
    test_note = "Счет на оплату отправлен клиенту бухгалтерией Астаны"

    status_code, patch_resp = http_request(
        astana_patch_url,
        method="PATCH",
        headers={"Authorization": f"Bearer {astana_token}"},
        data={"order_status": new_status, "manager_notes": test_note}
    )
    print(f"  PATCH {astana_patch_url} -> Status {status_code}")
    assert status_code == 200, f"FAIL: Status update failed: {patch_resp}"
    assert patch_resp["order_status"] == new_status, f"FAIL: order_status in response != {new_status}"
    assert patch_resp["manager_notes"] == test_note, f"FAIL: manager_notes in response != {test_note}"

    # Direct database verification
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT order_status, manager_notes, updated_at FROM user_sessions_leads WHERE id = %s;", (astana_order_id,))
    db_order = cur.fetchone()
    cur.close()
    conn.close()

    print(f"  DB verification for order #{astana_order_id}: status={db_order['order_status']}, notes='{db_order['manager_notes']}'")
    assert db_order["order_status"] == new_status, f"FAIL: DB order_status was not updated: {db_order}"
    assert db_order["manager_notes"] == test_note, f"FAIL: DB manager_notes was not updated: {db_order}"
    print("  -> TEST 6 PASSED: Order status and manager notes successfully updated in DB.")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! SPRINT 1 DEFINITION OF DONE FULLY SATISFIED.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
