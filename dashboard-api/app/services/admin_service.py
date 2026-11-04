"""
Admin Service: Telegram Managers RBAC and XLSX / WebApp Price Management.
"""

import io
import logging
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.database import get_db_cursor
from app.services.catalog_exporter import export_catalog_to_file

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. TELEGRAM MANAGERS RBAC (РОЛИ И ДОСТУП)
# ==============================================================================

def get_manager(telegram_id: int) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT id, telegram_id, full_name, username, role, is_active, created_at, updated_at
            FROM allowed_managers
            WHERE telegram_id = %s;
            """,
            (telegram_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def is_manager_allowed(telegram_id: int) -> bool:
    mgr = get_manager(telegram_id)
    return bool(mgr and mgr.get("is_active"))


def is_admin(telegram_id: int) -> bool:
    mgr = get_manager(telegram_id)
    return bool(mgr and mgr.get("is_active") and mgr.get("role") in ("superadmin", "admin"))


def list_all_managers() -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT id, telegram_id, full_name, username, role, is_active, created_at, updated_at
            FROM allowed_managers
            ORDER BY 
                CASE role 
                    WHEN 'superadmin' THEN 1 
                    WHEN 'admin' THEN 2 
                    ELSE 3 
                END, 
                id ASC;
            """
        )
        return [dict(r) for r in cur.fetchall()]


def add_or_update_manager(
    telegram_id: int, 
    full_name: str, 
    username: Optional[str] = None, 
    role: str = "manager",
    created_by: Optional[int] = None
) -> Dict[str, Any]:
    role_clean = role.lower() if role in ("superadmin", "admin", "manager") else "manager"
    with get_db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO allowed_managers (telegram_id, full_name, username, role, is_active, created_by, updated_at)
            VALUES (%s, %s, %s, %s, true, %s, NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                username = COALESCE(EXCLUDED.username, allowed_managers.username),
                role = EXCLUDED.role,
                is_active = true,
                updated_at = NOW()
            RETURNING id, telegram_id, full_name, username, role, is_active;
            """,
            (telegram_id, full_name.strip(), username.strip() if username else None, role_clean, created_by)
        )
        return dict(cur.fetchone())


def toggle_manager_status(telegram_id: int, is_active: bool) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            """
            UPDATE allowed_managers 
            SET is_active = %s, updated_at = NOW()
            WHERE telegram_id = %s
            RETURNING id, telegram_id, full_name, role, is_active;
            """,
            (is_active, telegram_id)
        )
        row = cur.fetchone()
        return dict(row) if row else None


# ==============================================================================
# 2. PRICE MANAGEMENT (EXCEL XLSX & WEBAPP)
# ==============================================================================

def export_pricelist_to_excel() -> bytes:
    """
    Generates a professionally styled Excel workbook containing all 165 products
    with current KZT prices, EUR base prices, and custom price override column.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Прайс-лист Tork"

    # Ensure grid lines are visible
    ws.views.sheetView[0].showGridLines = True

    # Colors
    navy_fill = PatternFill(start_color="003865", end_color="003865", fill_type="solid")
    cyan_fill = PatternFill(start_color="009FDA", end_color="009FDA", fill_type="solid")
    light_blue_fill = PatternFill(start_color="F0F9FF", end_color="F0F9FF", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    font_title = Font(name="Calibri", size=15, bold=True, color="003865")
    font_sub = Font(name="Calibri", size=10, italic=True, color="475569")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_regular = Font(name="Calibri", size=10)

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # 1. Header Banner
    ws.merge_cells("A1:I1")
    ws["A1"] = "TORK КАЗАХСТАН — ОФИЦИАЛЬНЫЙ ПРАЙС-ЛИСТ B2B"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(vertical="center")

    ws.merge_cells("A2:I2")
    ws["A2"] = "Инструкция: для изменения цены введите новую сумму в колонку 'Новая цена KZT (₸)' и отправьте этот файл обратно боту."
    ws["A2"].font = font_sub
    ws["A2"].alignment = Alignment(vertical="center")

    # Empty row 3
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 8

    # 2. Table Column Headers
    headers = [
        ("A4", "Артикул", 12),
        ("B4", "Наименование товара", 44),
        ("C4", "Категория", 15),
        ("D4", "Система", 10),
        ("E4", "Цвет", 12),
        ("F4", "Базовая EUR (€)", 14),
        ("G4", "Новая цена KZT (₸)", 20),   # Editable Column!
        ("H4", "Текущая цена в каталоге (₸)", 22),
        ("I4", "Статус в каталоге", 16)
    ]

    ws.row_dimensions[4].height = 26
    for pos, label, width in headers:
        cell = ws[pos]
        cell.value = label
        cell.fill = navy_fill
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        col_letter = pos[0]
        ws.column_dimensions[col_letter].width = width

    # Highlight column G (Editable price) with light cyan accent
    ws["G4"].fill = cyan_fill

    # 3. Fetch data from DB
    query = """
    SELECT 
        p.sku,
        p.name,
        p.category,
        p.system_code,
        p.color,
        p.price_eur,
        p.custom_price_kzt,
        v.current_price_kzt,
        COALESCE(p.is_active_in_catalog, true) as is_active
    FROM products p
    JOIN v_products_active v ON p.sku = v.sku
    ORDER BY p.category ASC, p.system_code ASC, p.sku ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    row_idx = 5
    for r in rows:
        cat_ru = "Диспенсер" if r["category"] == "dispenser" else "Расходник"
        status_ru = "Активен" if r["is_active"] else "Отключен"

        ws[f"A{row_idx}"] = str(r["sku"]).strip()
        ws[f"B{row_idx}"] = r["name"] or ""
        ws[f"C{row_idx}"] = cat_ru
        ws[f"D{row_idx}"] = r["system_code"] or "–"
        ws[f"E{row_idx}"] = r["color"] or "Стандарт"
        ws[f"F{row_idx}"] = float(r["price_eur"]) if r["price_eur"] is not None else 0.0
        ws[f"G{row_idx}"] = float(r["custom_price_kzt"]) if r["custom_price_kzt"] is not None else None
        ws[f"H{row_idx}"] = float(r["current_price_kzt"]) if r["current_price_kzt"] is not None else 0.0
        ws[f"I{row_idx}"] = status_ru

        # Alignments & Formats
        ws[f"A{row_idx}"].alignment = Alignment(horizontal="center")
        ws[f"A{row_idx}"].font = font_bold
        ws[f"C{row_idx}"].alignment = Alignment(horizontal="center")
        ws[f"D{row_idx}"].alignment = Alignment(horizontal="center")
        ws[f"E{row_idx}"].alignment = Alignment(horizontal="center")
        ws[f"F{row_idx}"].number_format = '#,##0.00 €'
        ws[f"G{row_idx}"].number_format = '#,##0 ₸'
        ws[f"H{row_idx}"].number_format = '#,##0 ₸'
        ws[f"I{row_idx}"].alignment = Alignment(horizontal="center")

        # Color column G soft blue so user knows it's the target
        ws[f"G{row_idx}"].fill = light_blue_fill

        # Zebra striping on even rows (except col G)
        if row_idx % 2 == 0:
            for col in ["A", "B", "C", "D", "E", "F", "H", "I"]:
                ws[f"{col}{row_idx}"].fill = zebra_fill

        # Borders
        for col_i in range(1, 10):
            col_letter = get_column_letter(col_i)
            ws[f"{col_letter}{row_idx}"].border = thin_border

        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def import_pricelist_from_excel(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parses uploaded Excel workbook, updates custom_price_kzt in PostgreSQL,
    and automatically re-exports webapp/products.json.
    """
    buf = io.BytesIO(file_bytes)
    wb = openpyxl.load_workbook(buf, data_only=True)
    ws = wb.active

    updated_count = 0
    skipped_count = 0
    errors = []

    # Find row 4 (headers) and identify columns
    header_col_sku = 1      # Column A
    header_col_new_price = 7 # Column G (Новая цена KZT)

    updates = []

    for row in ws.iter_rows(min_row=5, values_only=True):
        if not row or len(row) < 7:
            continue
        raw_sku = row[0]
        if not raw_sku:
            continue
        
        sku = str(raw_sku).strip()
        new_price_val = row[6]  # Column G

        if new_price_val is None or str(new_price_val).strip() == "":
            skipped_count += 1
            continue

        try:
            # Clean up numeric string (replace spaces, commas, currency symbols)
            val_clean = str(new_price_val).replace("₸", "").replace(" ", "").replace(",", ".").strip()
            price_float = float(val_clean)
            if price_float < 0:
                errors.append(f"SKU {sku}: цена не может быть отрицательной ({price_float})")
                continue
            updates.append((round(price_float, 2), sku))
        except Exception as e:
            errors.append(f"SKU {sku}: некорректный формат цены '{new_price_val}': {e}")

    if updates:
        with get_db_cursor() as cur:
            for price_kzt, sku in updates:
                cur.execute(
                    """
                    UPDATE products
                    SET custom_price_kzt = %s
                    WHERE sku = %s;
                    """,
                    (price_kzt, sku)
                )
                updated_count += 1

        # Automatically re-export catalog for Mini App
        try:
            export_catalog_to_file()
        except Exception as e:
            logger.error(f"Failed to re-export products.json after excel import: {e}")

    return {
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "errors": errors,
        "total_processed": len(updates) + skipped_count
    }


def update_single_product_price(sku: str, price_kzt: float) -> Dict[str, Any]:
    """
    Direct single product price update for Telegram WebApp in-place edit.
    """
    sku_clean = str(sku).strip()
    if price_kzt < 0:
        raise ValueError("Цена не может быть отрицательной")

    with get_db_cursor() as cur:
        cur.execute(
            """
            UPDATE products
            SET custom_price_kzt = %s
            WHERE sku = %s
            RETURNING sku, name, custom_price_kzt;
            """,
            (round(price_kzt, 2), sku_clean)
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Товар с артикулом {sku_clean} не найден")

    export_catalog_to_file()

    return {
        "sku": row["sku"],
        "name": row["name"],
        "price_kzt": float(row["custom_price_kzt"])
    }

