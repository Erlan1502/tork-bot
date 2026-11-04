import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Response
from pydantic import BaseModel

from app.services.admin_service import (
    list_all_managers,
    add_or_update_manager,
    toggle_manager_status,
    export_pricelist_to_excel,
    import_pricelist_from_excel,
    update_single_product_price,
    is_admin,
    is_manager_allowed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin-tg", tags=["Admin Telegram Panel"])


class ManagerItem(BaseModel):
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    role: Optional[str] = "manager"


class ManagerToggleRequest(BaseModel):
    is_active: bool


class SinglePriceUpdate(BaseModel):
    price_kzt: float


def verify_admin_access(x_telegram_user_id: Optional[int] = Header(None, alias="X-Telegram-User-Id")):
    """
    Validates that the requester has superadmin or admin privileges.
    If no header is passed (internal call or dev mode), allows or falls back.
    """
    if x_telegram_user_id and not is_admin(x_telegram_user_id):
        raise HTTPException(status_code=403, detail="Доступ запрещен: требуются права администратора Tork")
    return x_telegram_user_id


# ==============================================================================
# 1. MANAGERS ENDPOINTS
# ==============================================================================

@router.get("/managers")
def get_managers():
    """
    Returns list of all registered Telegram managers and administrators.
    """
    return list_all_managers()


@router.post("/managers")
def create_or_update_manager(payload: ManagerItem):
    """
    Grants access or updates role/name for a Telegram user ID.
    """
    try:
        res = add_or_update_manager(
            telegram_id=payload.telegram_id,
            full_name=payload.full_name,
            username=payload.username,
            role=payload.role or "manager"
        )
        return {"ok": True, "manager": res}
    except Exception as e:
        logger.error(f"Error adding manager: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/managers/{telegram_id}/toggle")
def toggle_manager(telegram_id: int, payload: ManagerToggleRequest):
    """
    Enables or disables manager access.
    """
    res = toggle_manager_status(telegram_id, payload.is_active)
    if not res:
        raise HTTPException(status_code=404, detail="Менеджер не найден")
    return {"ok": True, "manager": res}


# ==============================================================================
# 2. PRICE MANAGEMENT ENDPOINTS (XLSX & IN-PLACE)
# ==============================================================================

@router.get("/prices/export-excel")
def download_pricelist_excel():
    """
    Generates and returns official styled Excel pricelist (.xlsx).
    """
    excel_bytes = export_pricelist_to_excel()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=Tork_Pricelist_Kazakhstan.xlsx"
        }
    )


@router.post("/prices/import-excel")
async def upload_pricelist_excel(file: UploadFile = File(...)):
    """
    Accepts uploaded .xlsx workbook, updates custom_price_kzt in DB,
    and updates webapp/products.json immediately.
    """
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы Excel (.xlsx)")

    contents = await file.read()
    try:
        result = import_pricelist_from_excel(contents)
        return {"ok": True, "result": result}
    except Exception as e:
        logger.error(f"Error importing excel pricelist: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки Excel: {e}")


@router.patch("/prices/{sku}")
def update_product_price(sku: str, payload: SinglePriceUpdate):
    """
    Updates price for a single SKU in KZT and refreshes catalog.
    """
    try:
        res = update_single_product_price(sku, payload.price_kzt)
        return {"ok": True, "product": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating price for SKU {sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

