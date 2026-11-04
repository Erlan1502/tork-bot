#!/usr/bin/env python3
"""
End-to-End Test Suite for Phase 3: Interactive Post-Montage Scenario & Misclick Protection (Undo / Rollback).

Tests:
1. Database Schema & Migration:
   - Verifies 'previous_montage_state' column in user_sessions_leads (PostgreSQL).
   - Verifies migrations/007_previous_montage_state.sql and init.sql.
2. Initial State Setup & AI Montage Result:
   - Initializes manager session with a rendered photo montage for SKU 551000 (Tork Matic H1).
   - Verifies post-montage inline keyboard:
     [ 📊 Скачать презентацию (PDF) ]
     [ 🔄 Выбрать другой диспенсер ]
3. Action: Click '🔄 Выбрать другой диспенсер':
   - Calls POST /api/manager/change-dispenser.
   - Verifies current montage and selected SKU are NOT deleted from the DB.
   - Verifies snapshot archived into user_sessions_leads.previous_montage_state.
   - Verifies session transitions to 'SELECTING_DISPENSER'.
4. Misclick Protection Warning & Undo Prompt:
   - Verifies warning message text:
     "Вы вернулись к каталогу для выбора другого оборудования.
      ⚠️ Нажали случайно? Нажмите кнопку ниже, чтобы вернуть текущий монтаж."
   - Verifies inline keyboard contains:
     [ ↩️ Вернуть предыдущий монтаж ] (callback_data: restore_previous_montage)
     [ 🛍 Открыть каталог ] (web_app)
5. Intermediate State Simulation:
   - Simulates manager browsing Mini App catalog and selecting a new SKU (460004 / H2).
   - Verifies active selected_sku changes to 460004, while previous_montage_state STILL retains 551000.
6. Action: Click '↩️ Вернуть предыдущий монтаж' (Undo / Rollback):
   - Calls POST /api/manager/restore-montage.
   - Verifies ZERO Gemini token consumption (tokens_consumed == 0, ai_recomputed == False).
   - Verifies session state in DB is immediately restored to SKU 551000.
   - Verifies restored photo delivery with original buttons:
     [ 📊 Скачать презентацию (PDF) ]
     [ 🔄 Выбрать другой диспенсер ]
7. n8n Workflow Graph Verification:
   - Verifies 'Send Manager Result Photo' buttons.
   - Verifies 'Handle Change Dispenser' and 'Handle Restore Montage' nodes.
   - Verifies 'Route by Event Type' routing for change_dispenser and restore_previous_montage.
"""

import sys
import os
import json
import urllib.request
import urllib.parse
from pathlib import Path
import psycopg2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8088")
TEST_MANAGER_TG_ID = 5699064827

# Minimal 10x10 dummy PNG base64 for test fixtures
DUMMY_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAGElEQVR42mNk+M9QzwAEjAwMDAwMDAwMBQAoAwMBj1Z0vwAAAABJRU5ErkJggg=="
)


def get_pg_connection():
    return psycopg2.connect(
        dbname="tork_bot_db",
        user="tork_admin",
        password="supersecret_tork_kz_pass",
        host="localhost",
        port=5433
    )


def test_1_database_schema_and_migration():
    print("=" * 75)
    print("TEST 1: PostgreSQL Schema & Migration 007 Validation")
    print("=" * 75)

    migration_file = ROOT / "migrations" / "007_previous_montage_state.sql"
    assert migration_file.exists(), "migrations/007_previous_montage_state.sql is missing"
    with open(migration_file, "r", encoding="utf-8") as f:
        mig_sql = f.read()
    assert "previous_montage_state" in mig_sql, "previous_montage_state not in migration 007"
    print("  ✅ Migration file 007_previous_montage_state.sql verified.")

    init_file = ROOT / "init.sql"
    with open(init_file, "r", encoding="utf-8") as f:
        init_sql = f.read()
    assert "previous_montage_state" in init_sql, "previous_montage_state not in init.sql"
    print("  ✅ init.sql verified with previous_montage_state JSONB column.")

    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'user_sessions_leads' 
          AND column_name = 'previous_montage_state';
    """)
    row = cur.fetchone()
    assert row is not None, "Column previous_montage_state does NOT exist in user_sessions_leads!"
    print(f"  ✅ PostgreSQL live table user_sessions_leads has column '{row[0]}' ({row[1]}).")
    cur.close()
    conn.close()


def test_2_initial_montage_state_setup():
    print("\n" + "=" * 75)
    print("TEST 2: Setup Initial AI-Montage Result for SKU 551000")
    print("=" * 75)

    conn = get_pg_connection()
    cur = conn.cursor()

    initial_bundle = [
        {
            "sku": "551000",
            "name": "Tork Matic® диспенсер для полотенец в рулонах H1",
            "system_code": "H1",
            "color": "white",
            "count": 1
        }
    ]

    cur.execute(
        """
        INSERT INTO user_sessions_leads (
            tg_user_id, tg_username, client_name, distributor_id,
            selected_sku, selected_bundle, before_image_url, last_rendered_image_url,
            current_step, previous_montage_state, updated_at
        ) VALUES (
            %s, 'test_manager', 'Менеджер Тест', 1,
            '551000', %s::jsonb, %s, %s,
            'MONTAGE_COMPLETED', NULL, NOW()
        )
        ON CONFLICT (tg_user_id) DO UPDATE SET
            selected_sku = '551000',
            selected_bundle = EXCLUDED.selected_bundle,
            before_image_url = EXCLUDED.before_image_url,
            last_rendered_image_url = EXCLUDED.last_rendered_image_url,
            current_step = 'MONTAGE_COMPLETED',
            previous_montage_state = NULL,
            updated_at = NOW();
        """,
        (
            TEST_MANAGER_TG_ID,
            json.dumps(initial_bundle, ensure_ascii=False),
            DUMMY_IMAGE_BASE64,
            DUMMY_IMAGE_BASE64
        )
    )
    conn.commit()

    cur.execute(
        "SELECT selected_sku, current_step, last_rendered_image_url IS NOT NULL FROM user_sessions_leads WHERE tg_user_id = %s;",
        (TEST_MANAGER_TG_ID,)
    )
    sku, step, has_img = cur.fetchone()
    print(f"  [DB Setup] Manager {TEST_MANAGER_TG_ID}: SKU={sku}, Step={step}, HasImage={has_img}")
    assert sku == "551000", "Expected SKU 551000"
    assert step == "MONTAGE_COMPLETED", "Expected step MONTAGE_COMPLETED"
    assert has_img is True, "Expected last_rendered_image_url to be present"
    print("  ✅ PASS: Initial montage state seeded successfully.")

    cur.close()
    conn.close()


def test_3_change_dispenser_logic_and_archiving():
    print("\n" + "=" * 75)
    print("TEST 3: Action '🔄 Выбрать другой диспенсер' & State Archiving")
    print("=" * 75)

    url = f"{BASE_URL}/api/manager/change-dispenser"
    payload = {
        "telegram_id": TEST_MANAGER_TG_ID,
        "chat_id": TEST_MANAGER_TG_ID,
        "callback_query_id": "test_callback_query_change",
        "send_to_telegram": False
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200 OK, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    print(f"  [API] Status: {data.get('status')}")
    print(f"  [API] Current step: {data.get('current_step')}")
    assert data.get("ok") is True, "Expected ok: true"
    assert data.get("status") == "archived", "Expected status: archived"
    assert data.get("current_step") == "SELECTING_DISPENSER", "Expected current_step: SELECTING_DISPENSER"

    # Verify Database state
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT selected_sku, last_rendered_image_url IS NOT NULL, current_step, previous_montage_state
        FROM user_sessions_leads WHERE tg_user_id = %s;
        """,
        (TEST_MANAGER_TG_ID,)
    )
    sku, has_active_img, step, prev_state = cur.fetchone()
    cur.close()
    conn.close()

    print(f"  [DB] Active selected_sku: {sku} (NOT deleted)")
    print(f"  [DB] Active last_rendered_image_url present: {has_active_img} (NOT deleted)")
    print(f"  [DB] Current step: {step}")
    print(f"  [DB] Archived state in previous_montage_state: {list(prev_state.keys()) if prev_state else None}")

    assert sku == "551000", "CRITICAL: selected_sku must NOT be deleted from DB!"
    assert has_active_img is True, "CRITICAL: last_rendered_image_url must NOT be deleted from DB!"
    assert prev_state is not None, "previous_montage_state must NOT be None"
    assert prev_state.get("selected_sku") == "551000", "Archived SKU must be 551000"
    assert prev_state.get("last_rendered_image_url") is not None, "Archived image must NOT be None"

    print("  ✅ PASS: State archived in previous_montage_state without deleting active session data.")


def test_4_misclick_protection_warning_and_keyboard():
    print("\n" + "=" * 75)
    print("TEST 4: Accidental Misclick Protection Message & Keyboard Validation")
    print("=" * 75)

    url = f"{BASE_URL}/api/manager/change-dispenser"
    payload = {"telegram_id": TEST_MANAGER_TG_ID}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    msg_text = data.get("message_text", "")
    reply_markup = data.get("reply_markup", {})

    print(f"  [Bot Message]:\n{msg_text}\n")
    assert "Вы вернулись к каталогу для выбора другого оборудования" in msg_text, \
        "Expected return to catalog notice in message text"
    assert "Нажали случайно? Нажмите кнопку ниже, чтобы вернуть текущий монтаж" in msg_text, \
        "Expected undo / misclick prompt in message text"
    print("  ✅ PASS: Bot warning text matches exact specification.")

    # Validate Keyboard
    inline_kb = reply_markup.get("inline_keyboard", [])
    flat_buttons = [btn for row in inline_kb for btn in row]
    btn_texts = [b.get("text") for b in flat_buttons]
    print(f"  [Inline Buttons]: {btn_texts}")

    # Check button [ ↩️ Вернуть предыдущий монтаж ]
    restore_btn = next((b for b in flat_buttons if "Вернуть предыдущий монтаж" in b.get("text", "")), None)
    assert restore_btn is not None, "Missing button [ ↩️ Вернуть предыдущий монтаж ]"
    assert restore_btn.get("callback_data") == "restore_previous_montage", \
        f"Expected callback_data 'restore_previous_montage', got {restore_btn.get('callback_data')}"
    print(f"  ✅ PASS: Found Undo button: '{restore_btn['text']}' -> callback: {restore_btn['callback_data']}")

    # Check button [ 🛍 Открыть каталог ]
    catalog_btn = next((b for b in flat_buttons if "Открыть каталог" in b.get("text", "")), None)
    assert catalog_btn is not None, "Missing button [ 🛍 Открыть каталог ]"
    assert catalog_btn.get("web_app", {}).get("url"), "Catalog button must have a valid web_app URL"
    print(f"  ✅ PASS: Found Catalog Mini App button: '{catalog_btn['text']}' -> web_app url: {catalog_btn['web_app']['url']}")


def test_5_intermediate_catalog_selection():
    print("\n" + "=" * 75)
    print("TEST 5: Manager Selects New Dispenser (SKU 460004) in Catalog")
    print("=" * 75)

    conn = get_pg_connection()
    cur = conn.cursor()

    # Manager selects SKU 460004 (H2 Stainless Steel)
    new_bundle = [
        {
            "sku": "460004",
            "name": "Tork Xpress® диспенсер для полотенец Multifold",
            "system_code": "H2",
            "color": "stainless_steel",
            "count": 1
        }
    ]
    cur.execute(
        """
        UPDATE user_sessions_leads
        SET selected_sku = '460004',
            selected_bundle = %s::jsonb,
            updated_at = NOW()
        WHERE tg_user_id = %s;
        """,
        (json.dumps(new_bundle, ensure_ascii=False), TEST_MANAGER_TG_ID)
    )
    conn.commit()

    cur.execute(
        "SELECT selected_sku, previous_montage_state->>'selected_sku' FROM user_sessions_leads WHERE tg_user_id = %s;",
        (TEST_MANAGER_TG_ID,)
    )
    active_sku, prev_sku = cur.fetchone()
    cur.close()
    conn.close()

    print(f"  [DB] Active selected SKU: {active_sku}")
    print(f"  [DB] Preserved previous montage SKU: {prev_sku}")
    assert active_sku == "460004", "Active SKU should now be 460004"
    assert prev_sku == "551000", "Previous montage SKU must STILL be 551000 in archive!"
    print("  ✅ PASS: New catalog selection preserved previous montage archive safely.")


def test_6_undo_state_rollback_zero_tokens():
    print("\n" + "=" * 75)
    print("TEST 6: Instant Undo Rollback (0 Gemini Tokens & Zero Recomputation)")
    print("=" * 75)

    url = f"{BASE_URL}/api/manager/restore-montage"
    payload = {
        "telegram_id": TEST_MANAGER_TG_ID,
        "chat_id": TEST_MANAGER_TG_ID,
        "callback_query_id": "test_callback_query_restore",
        "send_to_telegram": False
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200 OK, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    print(f"  [API] Response status: {data.get('status')}")
    print(f"  [API] Restored SKU: {data.get('restored_sku')}")
    print(f"  [API] Tokens consumed: {data.get('tokens_consumed')}")
    print(f"  [API] AI recomputed: {data.get('ai_recomputed')}")

    assert data.get("ok") is True, "Expected ok: true"
    assert data.get("status") == "restored", "Expected status: restored"
    assert data.get("restored_sku") == "551000", "Expected restored SKU to be 551000"
    assert data.get("tokens_consumed") == 0, "CRITICAL: Must consume ZERO Gemini tokens!"
    assert data.get("ai_recomputed") is False, "CRITICAL: Must NOT recompute via AI!"
    assert data.get("has_rendered_image") is True, "Expected rendered image to be present"

    # Verify Database state
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT selected_sku, current_step, last_rendered_image_url IS NOT NULL FROM user_sessions_leads WHERE tg_user_id = %s;",
        (TEST_MANAGER_TG_ID,)
    )
    db_sku, db_step, db_has_img = cur.fetchone()
    cur.close()
    conn.close()

    print(f"  [DB] Restored DB SKU: {db_sku}")
    print(f"  [DB] Current step: {db_step}")
    assert db_sku == "551000", "Database selected_sku must be restored to 551000"
    assert db_step == "MONTAGE_RESTORED", "Database current_step must be MONTAGE_RESTORED"
    assert db_has_img is True, "Database last_rendered_image_url must be present"

    # Verify Restored Inline Keyboard
    reply_markup = data.get("reply_markup", {})
    inline_kb = reply_markup.get("inline_keyboard", [])
    flat_buttons = [btn for row in inline_kb for btn in row]
    btn_texts = [b.get("text") for b in flat_buttons]
    print(f"  [Restored Result Buttons]: {btn_texts}")

    pdf_btn = next((b for b in flat_buttons if "Скачать презентацию" in b.get("text", "")), None)
    change_btn = next((b for b in flat_buttons if "Выбрать другой диспенсер" in b.get("text", "")), None)

    assert pdf_btn is not None, "Missing button [ 📊 Скачать презентацию (PDF) ]"
    assert pdf_btn.get("callback_data") == "download_presentation", "PDF button callback mismatch"
    assert change_btn is not None, "Missing button [ 🔄 Выбрать другой диспенсер ]"
    assert change_btn.get("callback_data") == "change_dispenser", "Change dispenser button callback mismatch"

    print("  ✅ PASS: State restored instantly with 0 tokens and original result keyboard.")


def test_7_n8n_workflow_wiring():
    print("\n" + "=" * 75)
    print("TEST 7: n8n Workflow Graph & Node Integration")
    print("=" * 75)

    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        wf_data = json.load(f)
    wf = wf_data[0] if isinstance(wf_data, list) else wf_data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    connections = wf.get("connections", {})

    # 1. Send Manager Result Photo
    result_node = nodes.get("Send Manager Result Photo")
    assert result_node is not None, "Send Manager Result Photo node missing in workflow"
    rows = result_node.get("parameters", {}).get("inlineKeyboard", {}).get("rows", [])
    flat_buttons = [b for r in rows for b in r.get("row", {}).get("buttons", [])]
    btn_texts = [b.get("text") for b in flat_buttons]
    print(f"  [Workflow Result Photo Buttons]: {btn_texts}")

    pdf_btn = next((b for b in flat_buttons if "Скачать презентацию" in b.get("text", "")), None)
    change_btn = next((b for b in flat_buttons if "Выбрать другой диспенсер" in b.get("text", "")), None)
    assert pdf_btn is not None, "Missing [ 📊 Скачать презентацию (PDF) ] in Send Manager Result Photo"
    assert change_btn is not None, "Missing [ 🔄 Выбрать другой диспенсер ] in Send Manager Result Photo"
    assert change_btn.get("additionalFields", {}).get("callback_data") == "change_dispenser", \
        "Expected callback_data 'change_dispenser'"
    print("  ✅ Send Manager Result Photo inline keyboard verified.")

    # 2. Check Handler Nodes
    assert "Handle Change Dispenser" in nodes, "Handle Change Dispenser node missing in workflow"
    assert "Handle Restore Montage" in nodes, "Handle Restore Montage node missing in workflow"
    print("  ✅ 'Handle Change Dispenser' and 'Handle Restore Montage' HTTP nodes present.")

    # 3. Check Route by Event Type rules
    route_rules = nodes.get("Route by Event Type", {}).get("parameters", {}).get("rules", {}).get("values", [])
    rule_keys = [r.get("outputKey") for r in route_rules]
    print(f"  [Workflow Route Rules]: {rule_keys}")
    assert "change_dispenser" in rule_keys, "Route by Event Type missing 'change_dispenser' rule"
    assert "restore_previous_montage" in rule_keys, "Route by Event Type missing 'restore_previous_montage' rule"

    # 4. Check Connections
    route_conns = connections.get("Route by Event Type", {}).get("main", [])
    # Index 4 is Handle Change Dispenser, Index 5 is Handle Restore Montage
    assert any(c.get("node") == "Handle Change Dispenser" for c in route_conns[4]), \
        "Branch 4 must route to Handle Change Dispenser"
    assert any(c.get("node") == "Handle Restore Montage" for c in route_conns[5]), \
        "Branch 5 must route to Handle Restore Montage"
    print("  ✅ Route by Event Type connections to Change Dispenser and Restore Montage verified.")


if __name__ == "__main__":
    print("\n" + "#" * 75)
    print("# TORK KAZAKHSTAN: PHASE 3 E2E TEST SUITE")
    print("# INTERACTIVE POST-MONTAGE SCENARIO & MISCLICK PROTECTION (UNDO)")
    print("#" * 75 + "\n")

    try:
        test_1_database_schema_and_migration()
        test_2_initial_montage_state_setup()
        test_3_change_dispenser_logic_and_archiving()
        test_4_misclick_protection_warning_and_keyboard()
        test_5_intermediate_catalog_selection()
        test_6_undo_state_rollback_zero_tokens()
        test_7_n8n_workflow_wiring()
        print("\n" + "#" * 75)
        print("# ALL 7 TESTS PASSED SUCCESSFULLY! PHASE 3 IS FULLY OPERATIONAL!")
        print("#" * 75 + "\n")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
