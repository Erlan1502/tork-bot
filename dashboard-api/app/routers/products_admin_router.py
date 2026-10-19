import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user
from app.database import get_db_cursor
from app.models import Role
from app.schemas import (
    UserProfile,
    AdminProductItem,
    ProductToggleResponse,
)
from app.services.catalog_exporter import export_catalog_to_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/products", tags=["Products Management"])

def require_vendor_admin(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    if current_user.role != Role.VENDOR_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only vendor_admin can manage catalog products",
        )
    return current_user


@router.get("", response_model=List[AdminProductItem])
def get_admin_products(
    current_user: UserProfile = Depends(require_vendor_admin),
):
    """
    Returns list of all 165 products in catalog with active status flag and price in KZT.
    """
    with get_db_cursor() as cur:
        query = """
            SELECT 
                p.sku,
                p.name,
                p.category,
                p.system_code,
                p.price_eur,
                round(p.price_eur * COALESCE((
                    SELECT exchange_rates.rate
                    FROM exchange_rates
                    WHERE currency_from = 'EUR' AND currency_to = 'KZT'
                    ORDER BY updated_at DESC LIMIT 1
                ), 617.93), 2) AS current_price_kzt,
                COALESCE(p.is_focus_item, false) AS is_focus_item,
                COALESCE(p.is_active_in_catalog, true) AS is_active_in_catalog
            FROM products p
            ORDER BY p.sku ASC;
        """
        cur.execute(query)
        rows = cur.fetchall()

    items = [
        AdminProductItem(
            sku=str(r["sku"]).strip(),
            name=r["name"] or "",
            category=r["category"] or "dispenser",
            system_code=r["system_code"] or "",
            price_eur=float(r["price_eur"]) if r["price_eur"] is not None else None,
            current_price_kzt=float(r["current_price_kzt"]) if r["current_price_kzt"] is not None else 0.0,
            is_focus_item=bool(r["is_focus_item"]),
            is_active_in_catalog=bool(r["is_active_in_catalog"]),
        )
        for r in rows
    ]
    return items


@router.patch("/{sku}/toggle", response_model=ProductToggleResponse)
def toggle_product_active_status(
    sku: str,
    current_user: UserProfile = Depends(require_vendor_admin),
):
    """
    Toggles product active status (is_active_in_catalog) and re-exports ./webapp/products.json immediately.
    """
    sku_clean = str(sku).strip()

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT sku, name, COALESCE(is_active_in_catalog, true) AS is_active_in_catalog
            FROM products
            WHERE sku = %s;
        """, (sku_clean,))
        prod = cur.fetchone()

        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Товар с артикулом {sku_clean} не найден в базе данных",
            )

        current_status = bool(prod["is_active_in_catalog"])
        new_status = not current_status

        cur.execute("""
            UPDATE products 
            SET is_active_in_catalog = %s 
            WHERE sku = %s;
        """, (new_status, sku_clean))

    # Trigger instant catalog JSON re-export for Mini App
    try:
        active_count = export_catalog_to_file()
    except Exception as e:
        logger.error(f"Error while re-exporting catalog for SKU {sku_clean}: {e}")
        active_count = -1

    status_str = "активирован" if new_status else "отключен"
    message = f"Товар {sku_clean} ({prod['name']}) {status_str} в каталоге"

    return ProductToggleResponse(
        sku=sku_clean,
        name=prod["name"] or f"Tork {sku_clean}",
        is_active_in_catalog=new_status,
        message=message,
    )
