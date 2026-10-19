#!/usr/bin/env python3
"""
Sprint 3 End-to-End Test Suite:
Vendor Analytics, Catalog Matrix Management, and SLA Auditing.
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

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

def make_request(url, method="GET", data=None, token=None, headers=None):
    req_headers = headers.copy() if headers else {}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            body = data.encode("utf-8")
        elif isinstance(data, (bytes, bytearray)):
            body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
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
    except Exception as e:
        return 0, {}, str(e)


def login(email, password="TorkKZ2026!"):
    status, _, data = make_request(
        f"{BASE_URL}/api/admin/auth/login",
        method="POST",
        data={"email": email, "password": password}
    )
    assert status == 200, f"Login failed for {email}: {data}"
    return data["access_token"], data["user"]


def run_tests():
    print("=================================================================")
    print("▶ STARTING SPRINT 3 END-TO-END VALIDATION (ANALYTICS & CATALOG)")
    print("=================================================================")

    # -----------------------------------------------------------------
    # Step 1: Ensure DB Schema & Setup Known Orders for Analytics Verification
    # -----------------------------------------------------------------
    print("\n[1] Checking Database Schema & Seeding Analytics Test Orders...")
    conn = get_db_connection()
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check is_active_in_catalog column in products
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'products' AND column_name = 'is_active_in_catalog';
    """)
    assert cur.fetchone(), "FAIL: column is_active_in_catalog does not exist in products table!"
    print("  ✓ Column is_active_in_catalog verified in table products")

    # Seed controlled orders to verify exact analytics numbers
    # Astana (1), Almaty (2), Shymkent (3) with mixed channels and 1 breached SLA order (> 2 hours old)
    seed_orders = [
        # Order 101: Astana, Direct Catalog, Status: COMPLETED, reacted in 25 mins
        {
            "tg_user_id": 9101001,
            "tg_username": "astana_vip",
            "client_name": "Айдар Ахметов",
            "company_name": 'ТОО "Rixos President Astana"',
            "phone": "+7 (701) 777-11-22",
            "distributor_id": 1,
            "kp_number": "KP-AST-2026-101",
            "order_status": "COMPLETED",
            "lead_source": "direct_catalog",
            "created_hours_ago": 5.0,
            "updated_hours_ago": 4.58, # ~25 min reaction
            "selected_bundle": [
                {"sku": "551000", "name": "Tork Matic® полотенца H1", "price": 131340, "qty": 2, "line_total": 262680, "system_code": "H1"},
                {"sku": "100278", "name": "Tork полотенца Singlefold", "price": 3179.81, "qty": 10, "line_total": 31798.1, "system_code": "H3"}
            ]
        },
        # Order 102: Almaty, AI-Fitting, Status: NEW, created 4 hours ago -> SLA BREACHED!
        {
            "tg_user_id": 9102002,
            "tg_username": "almaty_hotel",
            "client_name": "Динара Сапарова",
            "company_name": 'ТОО "Almaty Grand Palace"',
            "phone": "+7 (702) 888-33-44",
            "distributor_id": 2,
            "kp_number": "KP-ALM-2026-102",
            "order_status": "NEW",
            "lead_source": "ai_fitting",
            "created_hours_ago": 4.0,
            "updated_hours_ago": 4.0,
            "selected_bundle": [
                {"sku": "560000", "name": "Tork диспенсер для мыла S4", "price": 45000, "qty": 4, "line_total": 180000, "system_code": "S4"}
            ]
        },
        # Order 103: Shymkent, Direct Catalog, Status: NEW, created 30 mins ago -> SLA OK (< 2h)
        {
            "tg_user_id": 9103003,
            "tg_username": "shymkent_med",
            "client_name": "Ербол Касымов",
            "company_name": 'ТОО "Клиника Shymkent Care"',
            "phone": "+7 (705) 999-55-66",
            "distributor_id": 3,
            "kp_number": "KP-SHY-2026-103",
            "order_status": "NEW",
            "lead_source": "direct_catalog",
            "created_hours_ago": 0.5,
            "updated_hours_ago": 0.5,
            "selected_bundle": [
                {"sku": "552000", "name": "Tork диспенсер для туалетной бумаги T2", "price": 32000, "qty": 3, "line_total": 96000, "system_code": "T2"}
            ]
        }
    ]

    for o in seed_orders:
        cur.execute("""
            INSERT INTO user_sessions_leads (
                tg_user_id, tg_username, client_name, company_name, phone,
                distributor_id, kp_number, order_status, current_step, lead_source,
                selected_bundle, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'ORDER_COMPLETED', %s, %s::jsonb,
                NOW() - (%s || ' hours')::interval,
                NOW() - (%s || ' hours')::interval
            )
            ON CONFLICT (tg_user_id) DO UPDATE SET
                client_name = EXCLUDED.client_name,
                company_name = EXCLUDED.company_name,
                phone = EXCLUDED.phone,
                distributor_id = EXCLUDED.distributor_id,
                kp_number = EXCLUDED.kp_number,
                order_status = EXCLUDED.order_status,
                current_step = 'ORDER_COMPLETED',
                lead_source = EXCLUDED.lead_source,
                selected_bundle = EXCLUDED.selected_bundle,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at;
        """, (
            o["tg_user_id"], o["tg_username"], o["client_name"], o["company_name"], o["phone"],
            o["distributor_id"], o["kp_number"], o["order_status"], o["lead_source"],
            json.dumps(o["selected_bundle"]), o["created_hours_ago"], o["updated_hours_ago"]
        ))
    cur.close()
    conn.close()
    print("  ✓ Analytics test orders seeded successfully in PostgreSQL")

    # -----------------------------------------------------------------
    # Step 2: RBAC Protection Verification (403 for Manager, 200 for Vendor)
    # -----------------------------------------------------------------
    print("\n[2] Testing RBAC Security & 403 Forbidden for Distributor Manager...")
    vendor_token, vendor_user = login("admin@tork.kz")
    astana_token, astana_user = login("astana@tork.kz")

    assert vendor_user["role"] == "vendor_admin"
    assert astana_user["role"] == "distributor_manager"

    protected_endpoints = [
        ("GET", f"{BASE_URL}/api/admin/analytics/summary"),
        ("GET", f"{BASE_URL}/api/admin/analytics/top-products"),
        ("GET", f"{BASE_URL}/api/admin/analytics/sla"),
        ("GET", f"{BASE_URL}/api/admin/products"),
        ("PATCH", f"{BASE_URL}/api/admin/products/551000/toggle"),
    ]

    for method, url in protected_endpoints:
        status, _, resp = make_request(url, method=method, token=astana_token)
        assert status == 403, f"Expected 403 Forbidden for manager on {method} {url}, got {status}: {resp}"
        print(f"  ✓ Blocked distributor manager with 403 on {method} {url.split('/api/admin')[-1]}")

    print("\n[3] Testing Vendor Admin Access (Expected 200 OK)...")
    for method, url in protected_endpoints[:4]:
        status, _, resp = make_request(url, method=method, token=vendor_token)
        assert status == 200, f"Expected 200 OK for vendor on {method} {url}, got {status}: {resp}"
        print(f"  ✓ Vendor admin authorized (200 OK) on {method} {url.split('/api/admin')[-1]}")

    # -----------------------------------------------------------------
    # Step 3: Analytics Summary & Aggregation Verification
    # -----------------------------------------------------------------
    print("\n[4] Verifying /api/admin/analytics/summary Metrics...")
    status, _, summary = make_request(f"{BASE_URL}/api/admin/analytics/summary", token=vendor_token)
    assert status == 200
    assert "total_revenue_kzt" in summary and summary["total_revenue_kzt"] > 0
    assert "total_orders_count" in summary and summary["total_orders_count"] >= 3
    assert "average_check_kzt" in summary and summary["average_check_kzt"] > 0
    assert "by_region" in summary and len(summary["by_region"]) == 3
    assert "by_channel" in summary
    assert "direct_catalog_count" in summary["by_channel"]
    assert "ai_fitting_count" in summary["by_channel"]

    print(f"  ✓ Total Revenue: {summary['total_revenue_kzt']:,.2f} KZT")
    print(f"  ✓ Total Orders: {summary['total_orders_count']}")
    print(f"  ✓ Average Check: {summary['average_check_kzt']:,.0f} KZT")
    print(f"  ✓ Channel Funnel: {summary['by_channel']}")
    for r in summary["by_region"]:
        print(f"    - Region #{r['distributor_id']} ({r['city']}): {r['revenue_kzt']:,.2f} KZT ({r['share_percent']}%), {r['orders_count']} orders")

    # -----------------------------------------------------------------
    # Step 4: Top-10 Demanded SKUs Verification
    # -----------------------------------------------------------------
    print("\n[5] Verifying /api/admin/analytics/top-products Aggregation...")
    status, _, top_prods = make_request(f"{BASE_URL}/api/admin/analytics/top-products", token=vendor_token)
    assert status == 200
    assert isinstance(top_prods, list) and len(top_prods) > 0
    assert len(top_prods) <= 10
    top_sku_entry = top_prods[0]
    for key in ("sku", "name", "system_code", "total_qty", "total_revenue_kzt"):
        assert key in top_sku_entry, f"Missing key {key} in top product entry: {top_sku_entry}"
    print(f"  ✓ Top product #1: SKU {top_sku_entry['sku']} ({top_sku_entry['name']}) System: {top_sku_entry['system_code']} | Qty: {top_sku_entry['total_qty']} | Revenue: {top_sku_entry['total_revenue_kzt']:,.2f} KZT")

    # -----------------------------------------------------------------
    # Step 5: SLA Audit & Breached Leads Verification
    # -----------------------------------------------------------------
    print("\n[6] Verifying /api/admin/analytics/sla Audit Metrics...")
    status, _, sla_data = make_request(f"{BASE_URL}/api/admin/analytics/sla", token=vendor_token)
    assert status == 200
    assert "average_response_time_minutes" in sla_data
    assert "average_response_time_formatted" in sla_data
    assert "breached_leads_count" in sla_data
    assert "breached_leads" in sla_data
    assert sla_data["breached_leads_count"] >= 1, "Expected at least 1 breached lead (KP-ALM-2026-102 seeded 4 hours ago)"

    breached_kps = [b["kp_number"] for b in sla_data["breached_leads"]]
    assert "KP-ALM-2026-102" in breached_kps, f"Expected KP-ALM-2026-102 in breached leads list: {breached_kps}"
    print(f"  ✓ Average SLA Reaction Time: {sla_data['average_response_time_formatted']} ({sla_data['average_response_time_minutes']} min)")
    print(f"  ✓ Breached leads detected (> 2 hrs waiting in NEW): {sla_data['breached_leads_count']}")
    for b in sla_data["breached_leads"][:3]:
        print(f"    - Lead #{b['id']} ({b['kp_number']}) | {b['company_name']} ({b['city']}) | Waiting: {b['wait_time_formatted']} (sla_breached={b['sla_breached']})")

    # -----------------------------------------------------------------
    # Step 6: Catalog Management & Instant products.json Sync
    # -----------------------------------------------------------------
    print("\n[7] Verifying Catalog Products List (165 Items)...")
    status, _, prods_list = make_request(f"{BASE_URL}/api/admin/products", token=vendor_token)
    assert status == 200
    assert len(prods_list) == 165, f"Expected 165 products in catalog, got {len(prods_list)}"
    p_sample = prods_list[0]
    for key in ("sku", "name", "category", "system_code", "current_price_kzt", "is_focus_item", "is_active_in_catalog"):
        assert key in p_sample, f"Missing key {key} in product item"
    print(f"  ✓ Received all 165 catalog products with prices and active flags")

    print("\n[8] Verifying SKU Toggle & Immediate ./webapp/products.json Sync...")
    root_dir = Path(__file__).resolve().parent.parent
    catalog_json_path = root_dir / "webapp" / "products.json"
    assert catalog_json_path.exists(), f"products.json not found at {catalog_json_path}"

    with open(catalog_json_path, "r", encoding="utf-8") as f:
        initial_catalog = json.load(f)
    initial_count = len(initial_catalog)

    test_sku = "551000"
    print(f"  Target SKU to toggle: {test_sku}")
    print(f"  Initial products count in products.json: {initial_count}")

    # Toggle OFF
    status, _, toggle_off_res = make_request(
        f"{BASE_URL}/api/admin/products/{test_sku}/toggle",
        method="PATCH",
        token=vendor_token
    )
    assert status == 200, f"Toggle off failed: {toggle_off_res}"
    assert toggle_off_res["is_active_in_catalog"] is False
    print(f"  ✓ API toggle response: {toggle_off_res['message']}")

    # Verify DB status is False
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_active_in_catalog FROM products WHERE sku = %s;", (test_sku,))
    assert cur.fetchone()[0] is False, "DB status was not updated to False!"
    cur.close()
    conn.close()
    print("  ✓ PostgreSQL products table confirmed: is_active_in_catalog = FALSE")

    # Verify webapp/products.json does NOT contain test_sku
    time.sleep(0.5)
    with open(catalog_json_path, "r", encoding="utf-8") as f:
        updated_catalog_off = json.load(f)
    assert not any(x["sku"] == test_sku for x in updated_catalog_off), f"SKU {test_sku} still found in products.json after deactivation!"
    assert len(updated_catalog_off) == initial_count - 1, f"Expected {initial_count - 1} items in products.json, got {len(updated_catalog_off)}"
    print(f"  ✓ products.json verified: SKU {test_sku} removed, total items: {len(updated_catalog_off)}")

    # Toggle back ON
    status, _, toggle_on_res = make_request(
        f"{BASE_URL}/api/admin/products/{test_sku}/toggle",
        method="PATCH",
        token=vendor_token
    )
    assert status == 200
    assert toggle_on_res["is_active_in_catalog"] is True
    print(f"  ✓ API toggle back ON response: {toggle_on_res['message']}")

    # Verify DB status is True
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_active_in_catalog FROM products WHERE sku = %s;", (test_sku,))
    assert cur.fetchone()[0] is True, "DB status was not restored to True!"
    cur.close()
    conn.close()
    print("  ✓ PostgreSQL products table confirmed: is_active_in_catalog = TRUE")

    # Verify webapp/products.json restored
    time.sleep(0.5)
    with open(catalog_json_path, "r", encoding="utf-8") as f:
        updated_catalog_on = json.load(f)
    assert any(x["sku"] == test_sku for x in updated_catalog_on), f"SKU {test_sku} not restored in products.json!"
    assert len(updated_catalog_on) == initial_count, f"Expected {initial_count} items in products.json, got {len(updated_catalog_on)}"
    print(f"  ✓ products.json restored with {len(updated_catalog_on)} items containing {test_sku}")

    # -----------------------------------------------------------------
    # Step 7: SPA Admin Interface Verification
    # -----------------------------------------------------------------
    print("\n[9] Verifying Admin SPA Interface (/admin/)...")
    status, _, html_content = make_request(f"{BASE_URL}/admin/")
    assert status == 200
    html_text = html_content.decode("utf-8") if isinstance(html_content, bytes) else html_content
    assert "Сквозная аналитика" in html_text, "Analytics tab not found in SPA index.html"
    assert "Управление матрицей каталога" in html_text, "Catalog management tab not found in SPA index.html"
    assert "SLA > 2 ч" in html_text, "SLA badge indicator not found in SPA index.html"
    print("  ✓ Admin interface serves index.html with Analytics tabs, Catalog Matrix and SLA Badges")

    print("\n=================================================================")
    print("✅ ALL SPRINT 3 DoD & SPECIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=================================================================")

if __name__ == "__main__":
    run_tests()
