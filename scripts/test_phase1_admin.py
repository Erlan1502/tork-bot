import os
import sys
import io
import openpyxl

# Add dashboard-api to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dashboard-api")))

# Configure DB connection to port 5433 for local test
os.environ["POSTGRES_PORT"] = "5433"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_USER"] = "tork_admin"
os.environ["POSTGRES_PASSWORD"] = "supersecret_tork_kz_pass"
os.environ["POSTGRES_DB"] = "tork_bot_db"

from app.services.admin_service import (
    list_all_managers,
    add_or_update_manager,
    toggle_manager_status,
    is_manager_allowed,
    is_admin,
    export_pricelist_to_excel,
    import_pricelist_from_excel,
    update_single_product_price
)

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 65)
    print("PHASE 1 INTEGRATION TEST: ADMIN RBAC & EXCEL/WEBAPP PRICING")
    print("=" * 65)

    # -------------------------------------------------------------------------
    # 1. TEST MANAGERS RBAC
    # -------------------------------------------------------------------------
    print("\n[Step 1] Testing Managers RBAC...")
    managers = list_all_managers()
    print(f"  • Total managers in DB: {len(managers)}")
    for m in managers:
        print(f"    - ID: {m['telegram_id']} | {m['full_name']} | Роль: {m['role']} | Активен: {m['is_active']}")

    test_tg_id = 999888777
    print(f"\n[Step 2] Adding new manager: ID {test_tg_id} ('Айбек Сапаров')...")
    res = add_or_update_manager(test_tg_id, "Айбек Сапаров", username="aibek_tork", role="manager")
    print(f"  • Added: {res['full_name']} (Role: {res['role']})")
    assert is_manager_allowed(test_tg_id), "Manager should be allowed"
    assert not is_admin(test_tg_id), "Normal manager should not have admin role"
    print("  ✅ Access check PASSED")

    print(f"\n[Step 3] Deactivating manager ID {test_tg_id}...")
    toggle_manager_status(test_tg_id, is_active=False)
    assert not is_manager_allowed(test_tg_id), "Deactivated manager should NOT be allowed"
    print("  • Deactivated successfully")

    print(f"[Step 4] Reactivating manager ID {test_tg_id}...")
    toggle_manager_status(test_tg_id, is_active=True)
    assert is_manager_allowed(test_tg_id), "Reactivated manager should be allowed"
    print("  ✅ Status toggle test PASSED")

    # -------------------------------------------------------------------------
    # 2. TEST EXCEL PRICELIST EXPORT
    # -------------------------------------------------------------------------
    print("\n[Step 5] Exporting Pricelist to Excel (.xlsx)...")
    excel_bytes = export_pricelist_to_excel()
    print(f"  • Generated XLSX size: {len(excel_bytes)/1024:.1f} KB")

    out_xlsx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../generated_presentations/Tork_Pricelist_Kazakhstan_Sample.xlsx"))
    with open(out_xlsx_path, "wb") as f:
        f.write(excel_bytes)
    print(f"  • Saved sample to: {out_xlsx_path}")

    # Validate Workbook
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    rows_count = ws.max_row
    print(f"  • Excel Rows: {rows_count} (Headers + Products)")
    assert rows_count >= 165, f"Expected at least 165 product rows, got {rows_count}"
    print("  ✅ Excel export validation PASSED")

    # -------------------------------------------------------------------------
    # 3. TEST EXCEL PRICELIST IMPORT & RECALCULATION
    # -------------------------------------------------------------------------
    print("\n[Step 6] Simulating manager editing prices in Excel...")
    # Change price for 551000 (Matic) to 89,000 ₸ and 680008 (SmartOne) to 43,500 ₸ in Column G (Row 7)
    target_row_551000 = None
    target_row_680008 = None
    for r in range(5, ws.max_row + 1):
        sku = str(ws[f"A{r}"].value).strip()
        if sku == "551000":
            target_row_551000 = r
        elif sku == "680008":
            target_row_680008 = r

    assert target_row_551000 is not None, "SKU 551000 should be in Excel"
    assert target_row_680008 is not None, "SKU 680008 should be in Excel"

    ws[f"G{target_row_551000}"] = "89 000 ₸"
    ws[f"G{target_row_680008}"] = 43500

    mod_buf = io.BytesIO()
    wb.save(mod_buf)
    mod_bytes = mod_buf.getvalue()

    print("\n[Step 7] Importing modified Excel into database...")
    import_res = import_pricelist_from_excel(mod_bytes)
    print(f"  • Updated positions: {import_res['updated_count']}")
    print(f"  • Skipped (untouched): {import_res['skipped_count']}")
    print(f"  • Errors: {import_res['errors']}")
    assert import_res["updated_count"] >= 2, "At least 2 prices should be updated"

    # Verify directly from DB
    from app.database import get_db_cursor
    with get_db_cursor() as cur:
        cur.execute("SELECT sku, custom_price_kzt, current_price_kzt FROM v_products_active WHERE sku IN ('551000', '680008');")
        rows = {r['sku']: r for r in cur.fetchall()}
        print(f"  • DB Verification SKU 551000: {rows['551000']['current_price_kzt']} ₸")
        print(f"  • DB Verification SKU 680008: {rows['680008']['current_price_kzt']} ₸")
        assert float(rows['551000']['current_price_kzt']) == 89000.0, "Matic price should be 89000"
        assert float(rows['680008']['current_price_kzt']) == 43500.0, "SmartOne price should be 43500"

    print("  ✅ Excel Import & DB Update PASSED")

    # -------------------------------------------------------------------------
    # 4. TEST SINGLE PRICE IN-PLACE UPDATE (WEBAPP MODE)
    # -------------------------------------------------------------------------
    print("\n[Step 8] Testing single in-place price update (WebApp mode)...")
    single_res = update_single_product_price("564500", 36500.0) # S4 Foam Soap
    print(f"  • Updated {single_res['name']} ({single_res['sku']}): {single_res['price_kzt']} ₸")
    assert single_res['price_kzt'] == 36500.0

    print("  ✅ In-place price update PASSED")

    print("\n" + "=" * 65)
    print("🎉 ALL PHASE 1 TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    main()

