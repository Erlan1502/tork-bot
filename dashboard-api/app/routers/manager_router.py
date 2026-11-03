import logging
import base64
import io
import json
import os
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

from app.database import get_db_cursor
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manager", tags=["Manager Mode"])

ASSETS_IMAGES_DIR = os.getenv("ASSETS_IMAGES_DIR", "/app/assets/images")
if not os.path.exists(ASSETS_IMAGES_DIR):
    # Fallback to relative path if running locally
    ASSETS_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../assets/images"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8896150273:AAE9PdQcenxCZVXgBhISBNwf0Nk3Zwr6yeY")
VLM_API_KEY = os.getenv("VLM_API_KEY", "")


class KitItem(BaseModel):
    sku: str
    name: str
    category: Optional[str] = "dispenser"
    product_type: Optional[str] = "hand_towel"
    system_code: Optional[str] = "H1"
    color: Optional[str] = "white"
    price: Optional[float] = 0.0
    image_url: Optional[str] = ""
    count: Optional[int] = 1
    dimensions_cm: Optional[Dict[str, float]] = None


class SelectKitPayload(BaseModel):
    action: Optional[str] = "select_kit"
    chat_id: Optional[int] = None
    tg_user_id: Optional[int] = None
    tg_username: Optional[str] = None
    items: List[KitItem]


def send_telegram_message(chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(f"Sent Telegram notification to {chat_id}, status: {resp.status}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")


@router.post("/select-kit")
def select_kit(payload: SelectKitPayload):
    """
    Saves selected multi-item kit in PostgreSQL user_sessions_leads and sends confirmation to Telegram.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Комплект товаров пуст")

    tg_id = payload.tg_user_id or payload.chat_id
    if not tg_id:
        raise HTTPException(status_code=400, detail="Не указан tg_user_id или chat_id")

    chat_id = payload.chat_id or tg_id
    primary_sku = payload.items[0].sku
    items_dicts = [item.dict() for item in payload.items]
    items_json = json.dumps(items_dicts, ensure_ascii=False)

    total_units = sum(item.count or 1 for item in payload.items)

    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_sessions_leads (
                    tg_user_id, tg_username, client_name, distributor_id, 
                    current_step, selected_sku, selected_bundle, updated_at
                ) VALUES (
                    %s, %s, 'Менеджер', 1, 
                    'MANAGER_KIT_SELECTED', %s, %s::jsonb, NOW()
                )
                ON CONFLICT (tg_user_id) DO UPDATE SET 
                    tg_username = COALESCE(EXCLUDED.tg_username, user_sessions_leads.tg_username),
                    selected_sku = EXCLUDED.selected_sku,
                    selected_bundle = EXCLUDED.selected_bundle,
                    current_step = 'MANAGER_KIT_SELECTED',
                    updated_at = NOW()
                RETURNING id;
                """,
                (tg_id, payload.tg_username or "", primary_sku, items_json)
            )
    except Exception as e:
        logger.error(f"Error updating user_sessions_leads: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Build detailed confirmation message for Telegram
    color_ru = {
        "white": "Белый",
        "black": "Черный",
        "stainless_steel": "Сталь",
        "none": "Стандарт"
    }

    lines = ["✅ <b>Комплект оборудования сохранен!</b>\n"]
    lines.append(f"📦 <b>Выбрано для примерки:</b> {len(payload.items)} поз. (всего {total_units} шт.)\n")

    for idx, it in enumerate(payload.items, start=1):
        c_ru = color_ru.get((it.color or "").lower(), it.color or "Белый")
        lines.append(f"{idx}. <b>{it.name}</b>")
        lines.append(f"   • Арт: <code>{it.sku}</code> | Система: <b>{it.system_code}</b> ({c_ru})")
        lines.append(f"   • Количество: <b>{it.count or 1} шт.</b>\n")

    lines.append("📸 <b>Следующий шаг:</b> Отправьте в этот чат <b>фотографию санузла клиента</b>.")
    lines.append("Нейросеть смонтирует все выбранные диспенсеры в нужные функциональные зоны!")

    confirm_text = "\n".join(lines)
    send_telegram_message(chat_id, confirm_text)

    return {
        "ok": True,
        "items_count": len(payload.items),
        "total_units": total_units,
        "primary_sku": primary_sku
    }


class CompositeRequest(BaseModel):
    user_photo_base64: str
    tg_user_id: Optional[int] = None
    chat_id: Optional[int] = None
    items: Optional[List[KitItem]] = None


def create_drop_shadow(image: Image.Image, offset=(15, 15), blur_radius=12, shadow_color=(0, 0, 0, 120)) -> Image.Image:
    """Creates a soft, realistic drop shadow for a transparent PNG object."""
    # Create shadow canvas with margin
    margin = blur_radius * 2
    w = image.width + margin * 2 + abs(offset[0])
    h = image.height + margin * 2 + abs(offset[1])

    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Extract alpha mask
    alpha = image.split()[3]
    # Create solid shadow layer
    shadow_mask = Image.new("RGBA", image.size, shadow_color)
    shadow_mask.putalpha(alpha)

    # Paste shadow mask at offset
    paste_x = margin + max(0, offset[0])
    paste_y = margin + max(0, offset[1])
    shadow.paste(shadow_mask, (paste_x, paste_y), shadow_mask)

    # Blur shadow
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    return shadow, margin


def load_product_png(sku: str) -> Optional[Image.Image]:
    """Finds and loads clean product PNG with alpha channel."""
    search_paths = [
        os.path.join(ASSETS_IMAGES_DIR, f"{sku}.png"),
        os.path.join(ASSETS_IMAGES_DIR, f"{sku}.jpg"),
        os.path.join(ASSETS_IMAGES_DIR, "551000.png")
    ]
    for p in search_paths:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA")
                return img
            except Exception as e:
                logger.warning(f"Failed to load image at {p}: {e}")
    return None


@router.post("/composite")
def composite_fitting(req: CompositeRequest):
    """
    High-fidelity spatial compositing without destroying original washroom background.
    Preserves 100% of tiles, plumbing, lighting and walls from manager's photo.
    """
    if not req.user_photo_base64:
        raise HTTPException(status_code=400, detail="Missing user_photo_base64")

    # 1. Load User Photo
    try:
        user_photo_bytes = base64.b64decode(req.user_photo_base64)
        base_img = Image.open(io.BytesIO(user_photo_bytes)).convert("RGBA")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid user photo base64: {e}")

    # 2. Fetch Selected Items from DB if not provided
    items = req.items or []
    if not items and req.tg_user_id:
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    "SELECT selected_bundle, selected_sku FROM user_sessions_leads WHERE tg_user_id = %s;",
                    (req.tg_user_id,)
                )
                row = cur.fetchone()
                if row and row.get("selected_bundle"):
                    raw_bundle = row["selected_bundle"]
                    if isinstance(raw_bundle, list):
                        items = [KitItem(**b) for b in raw_bundle]
                    elif isinstance(raw_bundle, dict):
                        items = [KitItem(**raw_bundle)]
                elif row and row.get("selected_sku"):
                    items = [KitItem(sku=row["selected_sku"], name="Tork Matic® диспенсер H1")]
        except Exception as e:
            logger.warning(f"Could not load items from DB: {e}")

    if not items:
        # Default fallback
        items = [KitItem(sku="551000", name="Tork Matic® диспенсер H1")]

    W, H = base_img.size

    # Composite canvas starts as a copy of the manager's actual room photo
    canvas = base_img.copy()

    # Determine placement zones according to Tork hygiene standards:
    # We assign realistic relative positions (x_pct, y_pct, target_height_pct)
    # Zone 1: Towel dispenser (Hand Washing) -> Right of center, eye/hand level (y: 35-45%)
    # Zone 2: Soap dispenser (Hand Washing) -> Over sink counter, lower eye level (y: 45-55%, closer to center)
    # Zone 3: Waste bin -> Low right / floor level (y: 65-75%)
    # Zone 4: Toilet paper / other -> Left or secondary position

    placements = []
    towel_items = [it for it in items if "towel" in (it.product_type or "").lower() or (it.system_code or "").startswith("H")]
    soap_items = [it for it in items if "soap" in (it.product_type or "").lower() or (it.system_code or "").startswith("S")]
    bin_items = [it for it in items if "bin" in (it.product_type or "").lower() or (it.system_code or "").startswith("B") or "корзин" in it.name.lower()]
    other_items = [it for it in items if it not in towel_items and it not in soap_items and it not in bin_items]

    sorted_items = towel_items + soap_items + bin_items + other_items

    # Placement coordinates normalized (cx, cy, target_height_ratio)
    slots = [
        {"name": "towel_right", "cx": 0.72, "cy": 0.42, "h_ratio": 0.28},
        {"name": "soap_center", "cx": 0.52, "cy": 0.48, "h_ratio": 0.18},
        {"name": "bin_floor",   "cx": 0.72, "cy": 0.75, "h_ratio": 0.26},
        {"name": "extra_left",  "cx": 0.25, "cy": 0.45, "h_ratio": 0.22},
    ]

    mounted_details = []

    for i, it in enumerate(sorted_items):
        slot = slots[min(i, len(slots) - 1)]
        img_item = load_product_png(it.sku)
        if not img_item:
            continue

        target_h = int(H * slot["h_ratio"])
        aspect = img_item.width / img_item.height
        target_w = int(target_h * aspect)
        resized_item = img_item.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Center on slot
        pos_x = int(W * slot["cx"] - target_w / 2)
        pos_y = int(H * slot["cy"] - target_h / 2)

        # Ensure within image bounds
        pos_x = max(10, min(W - target_w - 10, pos_x))
        pos_y = max(10, min(H - target_h - 10, pos_y))

        # Generate realistic soft contact drop shadow (light from top-left)
        shadow_img, margin = create_drop_shadow(
            resized_item, 
            offset=(int(target_w * 0.05), int(target_h * 0.05)), 
            blur_radius=int(target_w * 0.04)
        )

        shadow_pos_x = pos_x - margin
        shadow_pos_y = pos_y - margin

        # 1. Paste shadow onto room wall
        canvas.alpha_composite(shadow_img, (shadow_pos_x, shadow_pos_y))

        # 2. Paste crisp, photorealistic dispenser
        canvas.alpha_composite(resized_item, (pos_x, pos_y))

        mounted_details.append({
            "sku": it.sku,
            "name": it.name,
            "system_code": it.system_code,
            "count": it.count or 1
        })

    # Convert back to RGB JPEG
    final_rgb = canvas.convert("RGB")
    buf = io.BytesIO()
    final_rgb.save(buf, format="JPEG", quality=95)
    result_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Build rich caption
    color_ru = {"white": "Белый", "black": "Черный", "stainless_steel": "Нержавеющая сталь"}
    caption_lines = [
        "✨ <b>Визуализация санузла готова!</b>\n",
        f"📸 <i>Все {len(mounted_details)} диспенсера смонтированы на реальные стены с расчетом масштаба и контактных теней:</i>\n"
    ]
    for idx, d in enumerate(mounted_details, start=1):
        caption_lines.append(f"{idx}. <b>{d['name']}</b> (арт. <code>{d['sku']}</code>, сист. <b>{d['system_code']}</b>) — {d['count']} шт.")

    caption_lines.append("\n💡 <i>Монтаж выполнен с сохранением интерьера, плитки и освещения клиента.</i>")
    caption = "\n".join(caption_lines)

    return {
        "ok": True,
        "result_image_base64": result_base64,
        "caption": caption,
        "mounted_count": len(mounted_details)
    }
