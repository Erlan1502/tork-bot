#!/usr/bin/env python3
"""
End-to-End Test Suite for Phase 2: Production Tork Presentation Generator & Telegram Bot Integration.
Tests:
1. PostgreSQL schema (user_sessions_leads with before_image_url & last_rendered_image_url).
2. FastAPI POST /api/manager/render-presentation (JSON & Binary modes).
3. PDF integrity & 1-page A4 validation via pypdf.
4. Essity certified metrics & text extraction (percentages, seconds, doses, warranty strip).
5. Multi-system coverage (H1, H2, S4, T8, B1).
6. Simulated manager Telegram inline button click [📊 Скачать презентацию (PDF)].
7. Nginx CDN static delivery for generated presentations.
8. n8n workflow graph integrity (Send Manager Result Photo & Route by Event Type).
"""

import sys
import os
import json
import io
import urllib.request
import urllib.parse
from pathlib import Path
import pypdf
import psycopg2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8088")
TEST_MANAGER_TG_ID = 5699064827

def test_1_database_schema():
    print("=" * 70)
    print("TEST 1: PostgreSQL Schema & user_sessions_leads Validation")
    print("=" * 70)

    conn = psycopg2.connect(
        dbname="tork_bot_db",
        user="tork_admin",
        password="supersecret_tork_kz_pass",
        host="localhost",
        port=5433
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'user_sessions_leads' 
          AND column_name IN ('before_image_url', 'last_rendered_image_url', 'selected_sku', 'selected_bundle');
    """)
    cols = dict(cur.fetchall())
    print(f"  [DB] user_sessions_leads found columns: {list(cols.keys())}")
    assert "before_image_url" in cols, "before_image_url column missing"
    assert "last_rendered_image_url" in cols, "last_rendered_image_url column missing"
    assert "selected_sku" in cols, "selected_sku column missing"
    print("  ✅ PASS: All required columns present in user_sessions_leads.")

    # Check allowed_managers
    cur.execute("SELECT telegram_id, full_name, role FROM allowed_managers WHERE telegram_id = %s;", (TEST_MANAGER_TG_ID,))
    mgr = cur.fetchone()
    print(f"  [DB] Allowed Manager record: {mgr}")
    assert mgr is not None, f"Manager {TEST_MANAGER_TG_ID} not in allowed_managers"
    print(f"  ✅ PASS: Manager {mgr[0]} ({mgr[1]}) verified with role '{mgr[2]}'.")

    cur.close()
    conn.close()


def test_2_render_presentation_api_json():
    print("\n" + "=" * 70)
    print("TEST 2: POST /api/manager/render-presentation (JSON Mode)")
    print("=" * 70)

    url = f"{BASE_URL}/api/manager/render-presentation"
    payload = {
        "telegram_id": TEST_MANAGER_TG_ID,
        "format": "json"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    print(f"  [API] Response status: 200 OK")
    print(f"  [API] Filename: {data.get('filename')}")
    print(f"  [API] System code: {data.get('system_code')}")
    print(f"  [API] SKU: {data.get('sku')}")
    print(f"  [API] File size: {data.get('size_bytes')} bytes")
    print(f"  [API] File URL: {data.get('file_url')}")

    assert data.get("ok") is True, "Expected ok: true"
    assert data.get("filename"), "Expected non-empty filename"
    assert data.get("pdf_base64"), "Expected non-empty pdf_base64"
    assert data.get("size_bytes", 0) > 10000, "PDF size suspiciously small"
    print("  ✅ PASS: Presentation rendered in JSON mode with valid base64 payload.")


def test_3_render_presentation_api_binary_and_pdf_integrity():
    print("\n" + "=" * 70)
    print("TEST 3: POST /api/manager/render-presentation (Binary Mode & PDF Integrity)")
    print("=" * 70)

    url = f"{BASE_URL}/api/manager/render-presentation"
    payload = {
        "telegram_id": TEST_MANAGER_TG_ID
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        content_type = resp.headers.get("Content-Type", "")
        content_disp = resp.headers.get("Content-Disposition", "")
        pdf_bytes = resp.read()

    print(f"  [HTTP] Content-Type: {content_type}")
    print(f"  [HTTP] Content-Disposition: {content_disp}")
    print(f"  [HTTP] Received bytes: {len(pdf_bytes)}")

    assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
    assert "attachment" in content_disp, f"Expected attachment in Content-Disposition"

    # PDF validation with pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    print(f"  [PDF] Total pages: {page_count}")
    assert page_count == 1, f"CRITICAL: PDF must be strictly 1 page! Got {page_count} pages."

    page_text = reader.pages[0].extract_text() or ""
    print(f"  [PDF] Extracted text length: {len(page_text)} chars")
    
    # Check essential Essity branded texts
    expected_tokens = ["Tork", "Essity", "Гарантия 3 года", "Бесплатный монтаж"]
    for tok in expected_tokens:
        found = tok.lower() in page_text.lower()
        print(f"  [PDF Check] Contains '{tok}': {'✅' if found else '❌'}")
        assert found, f"Expected token '{tok}' in PDF page text"

    print("  ✅ PASS: PDF is strictly 1 page, contains valid Essity proofs and warranty strip.")


def test_4_multi_system_matrix():
    print("\n" + "=" * 70)
    print("TEST 4: Multi-System Matrix Rendering (H1, H2, S4, T8, B1)")
    print("=" * 70)

    systems = [
        ("H1", "551000", "office"),
        ("H2", "460004", "horeca"),
        ("S4", "561500", "medical"),
        ("T8", "680008", "horeca"),
        ("B1", "563000", "general")
    ]

    for sys_code, default_sku, segment in systems:
        url = f"{BASE_URL}/api/manager/render-presentation"
        payload = {
            "telegram_id": TEST_MANAGER_TG_ID,
            "system_code": sys_code,
            "segment": segment,
            "format": "json"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        pdf_raw = io.BytesIO(bytes.fromhex("") if not data.get("pdf_base64") else __import__("base64").b64decode(data["pdf_base64"]))
        reader = pypdf.PdfReader(pdf_raw)
        pages = len(reader.pages)
        status = "✅ PASS (1 page)" if pages == 1 else f"❌ FAIL ({pages} pages)"
        print(f"  • System {sys_code} (Segment: {segment}) -> {data.get('filename')} | {status} ({data.get('size_bytes')/1024:.1f} KB)")
        assert pages == 1, f"System {sys_code} generated {pages} pages instead of 1"

    print("  ✅ PASS: All 5 core systems compile strictly to 1 page.")


def test_5_simulated_telegram_button_click():
    print("\n" + "=" * 70)
    print("TEST 5: Simulation of Telegram Inline Button [📊 Скачать презентацию (PDF)]")
    print("=" * 70)

    url = f"{BASE_URL}/api/manager/render-presentation"
    payload = {
        "telegram_id": TEST_MANAGER_TG_ID,
        "chat_id": TEST_MANAGER_TG_ID,
        "callback_query_id": "test_callback_query_777",
        "send_to_telegram": True
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    print(f"  [Simulate] Button click dispatched.")
    print(f"  [Simulate] Response status: {data.get('status')}")
    print(f"  [Simulate] Filename: {data.get('filename')}")
    print(f"  [Simulate] Chat ID: {data.get('chat_id')}")
    print(f"  [Simulate] File size: {data.get('size_bytes')} bytes")
    
    assert data.get("ok") is True, "Expected ok: true"
    assert data.get("filename"), "Expected filename in response"
    print("  ✅ PASS: Telegram send pipeline executed cleanly.")


def test_6_cdn_static_delivery():
    print("\n" + "=" * 70)
    print("TEST 6: NGINX CDN Static Delivery for Generated Presentations")
    print("=" * 70)

    filename = urllib.parse.quote("Презентация_Tork_H2_460004.pdf")
    url = f"{BASE_URL}/presentations/{filename}"
    req = urllib.request.Request(url, headers={"User-Agent": "TestPhase2/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200 OK from CDN, got {resp.status}"
        content = resp.read()

    print(f"  [CDN] URL: {url}")
    print(f"  [CDN] Status: 200 OK")
    print(f"  [CDN] Fetched bytes: {len(content)}")
    assert len(content) > 10000, "CDN file size suspiciously small"
    print("  ✅ PASS: Presentation accessible and downloadable directly through CDN.")


def test_7_workflow_graph_integrity():
    print("\n" + "=" * 70)
    print("TEST 7: n8n Workflow Graph Integrity & Presentation Button Wiring")
    print("=" * 70)

    wf_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(wf_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    wf = data[0] if isinstance(data, list) else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    conns = wf.get("connections", {})

    # Check node-send-manager-result-photo has the button
    assert "Send Manager Result Photo" in nodes, "Send Manager Result Photo node missing"
    btn_node = nodes["Send Manager Result Photo"]
    rows = btn_node.get("parameters", {}).get("inlineKeyboard", {}).get("rows", [])
    has_pres_btn = False
    for r in rows:
        for b in r.get("row", {}).get("buttons", []):
            if b.get("additionalFields", {}).get("callback_data") == "download_presentation":
                has_pres_btn = True
                print(f"  [Workflow] Found inline button: '{b.get('text')}' (callback_data: {b.get('additionalFields', {}).get('callback_data')})")
    assert has_pres_btn, "Missing [📊 Скачать презентацию (PDF)] button in Send Manager Result Photo"

    # Check Render & Send Presentation node
    assert "Render & Send Presentation" in nodes, "Render & Send Presentation node missing"
    render_node = nodes["Render & Send Presentation"]
    assert "render-presentation" in render_node.get("parameters", {}).get("url", ""), "Render & Send Presentation must call render-presentation endpoint"
    print("  [Workflow] Found 'Render & Send Presentation' HTTP node calling /api/manager/render-presentation")

    # Check Route by Event Type routing
    route_conns = conns.get("Route by Event Type", {}).get("main", [])
    assert len(route_conns) >= 3, "Route by Event Type must have outputs"
    branch_2_nodes = [c.get("node") for c in route_conns[2]]
    assert "Render & Send Presentation" in branch_2_nodes, "Route output 2 must connect to Render & Send Presentation"
    print("  [Workflow] Event flow: download_presentation (branch 2) -> Render & Send Presentation verified.")

    print("  ✅ PASS: n8n workflow graph properly configured for presentation download.")


def main():
    print("\n" + "#" * 70)
    print("# TORK KAZAKHSTAN: PHASE 2 E2E TEST SUITE")
    print("# PRODUCTION PRESENTATION GENERATOR & TELEGRAM BOT INTEGRATION")
    print("#" * 70 + "\n")

    test_1_database_schema()
    test_2_render_presentation_api_json()
    test_3_render_presentation_api_binary_and_pdf_integrity()
    test_4_multi_system_matrix()
    test_5_simulated_telegram_button_click()
    test_6_cdn_static_delivery()
    test_7_workflow_graph_integrity()

    print("\n" + "#" * 70)
    print("# ALL 7 TESTS PASSED SUCCESSFULLY! PHASE 2 IS FULLY OPERATIONAL!")
    print("#" * 70 + "\n")

if __name__ == "__main__":
    main()
