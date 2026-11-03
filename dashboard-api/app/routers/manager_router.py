import logging
import base64
import io
import json
import os
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from PIL import Image, ImageFilter

from app.database import get_db_cursor
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manager", tags=["Manager Mode"])

ASSETS_IMAGES_DIR = os.getenv("ASSETS_IMAGES_DIR", "/app/assets/images")
if not os.path.exists(ASSETS_IMAGES_DIR):
    ASSETS_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../assets/images"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
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
    lines.append("Нейросеть смонтирует все выбранные диспенсеры в нужные функциональные зоны с учетом освещения и теней!")

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


def audit_washroom_and_reason_actions(user_photo_b64: str, items: List[KitItem]) -> Dict[str, Any]:
    """
    Image-to-Reasoning Layer (Gemini 2.5 Flash):
    Audits existing equipment in the washroom photo (old dispensers, electric hand dryers,
    soap bottles, waste bins, toilet paper holders).
    Reasons whether each selected Tork item should:
      - REPLACE an existing/broken/obsolete item in that functional zone, OR
      - ADD / COMPLEMENT a missing item on an empty wall/floor space.
    Also detects equipment to PRESERVE intact.
    """
    api_key = VLM_API_KEY or os.getenv("VLM_API_KEY", "")
    if not api_key:
        logger.warning("VLM_API_KEY not configured for equipment reasoning audit")
        return {}

    items_desc = []
    for idx, it in enumerate(items, start=1):
        items_desc.append(
            f"{idx}. SKU {it.sku}: '{it.name}' (System: {it.system_code or 'N/A'}, "
            f"Type: {it.product_type or 'hygiene dispenser'}, Color: {it.color or 'standard'})"
        )

    audit_prompt = (
        "You are an expert commercial hygiene auditor and architectural space planner for Tork (Essity).\n"
        "Analyze the provided photo of a commercial washroom/restroom.\n\n"
        "Selected Tork equipment bundle chosen by the manager for fitting:\n" +
        "\n".join(items_desc) + "\n\n"
        "Your objectives:\n"
        "1. Identify ALL existing hygiene fixtures in the photo:\n"
        "   - Hand drying devices (electric hand dryers, manual towel dispensers, loose paper towels).\n"
        "   - Soap dispensing units (wall-mounted soap dispensers, liquid soap pump bottles on countertops).\n"
        "   - Toilet paper dispensers / roll holders.\n"
        "   - Waste bins / receptacles (under sink, near door, freestanding).\n"
        "   Note their locations and visible conditions (e.g., outdated plastic, worn, broken electric dryer, loose bottle).\n\n"
        "2. Match and Reason the Action for EACH item in the chosen Tork bundle:\n"
        "   - If the room already has an old/competing device of that functional type (e.g., an old electric hand dryer or worn dispenser present, and manager chose a Tork hand towel dispenser; or old soap bottle on counter and manager chose Tork soap dispenser; or old bin and manager chose Tork bin): mark action as 'REPLACE'. Explain what is removed and replaced.\n"
        "   - If that functional zone is completely absent (e.g., no hand dryer or towel dispenser anywhere; or no soap dispenser): mark action as 'ADD'. Explain the best ergonomic mounting location.\n"
        "   - Note any existing equipment that should be 'PRESERVED' (e.g., existing toilet paper holder or mirror when not part of the upgrade bundle).\n\n"
        "3. Respond in strict JSON format:\n"
        "{\n"
        '  "existing_equipment": [{"type": "...", "location": "...", "condition": "..."}],\n'
        '  "plan": [\n'
        '    {\n'
        '      "sku": "...",\n'
        '      "action": "REPLACE" or "ADD",\n'
        '      "target_location": "...",\n'
        '      "replaces_item": "name of replaced item or null",\n'
        '      "summary_ru": "Краткое понятное описание действия на русском"\n'
        '    }\n'
        '  ],\n'
        '  "preserved_equipment": ["..."],\n'
        '  "telegram_audit_html": "HTML formatted text in Russian for Telegram: list of 🔄 Замены, ➕ Дооснащения, and 🛡️ Сохранено",\n'
        '  "generation_instructions": "Clear, precise English instructions for image inpainting detailing what to ERASE and where to MOUNT each Tork SKU"\n'
        "}\n"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": audit_prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": user_photo_b64}}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        logger.info(f"Running Image-to-Reasoning audit with Gemini 2.5 Flash for {len(items)} items...")
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if raw_text:
                result = json.loads(raw_text)
                logger.info(f"Reasoning audit complete: {len(result.get('plan', []))} actions planned.")
                return result
    except Exception as e:
        logger.warning(f"Error in Image-to-Reasoning audit: {e}")

    return {}


def call_gemini_photorealistic_fitting(
    user_photo_b64: str,
    items: List[KitItem],
    reasoning_plan: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Calls Google Gemini 3.1 Flash Image model for architectural inpainting.
    If reasoning_plan is provided, strictly erases old equipment (hand dryers, worn dispensers)
    and places new Tork products in their designated ergonomic positions.
    Preserves 100% of tiles, mirror, and untouched architecture.
    """
    api_key = VLM_API_KEY or os.getenv("VLM_API_KEY", "")
    if not api_key:
        logger.warning("VLM_API_KEY not configured for Gemini fitting")
        return None

    product_parts = []
    default_instructions = []

    for idx, it in enumerate(items, start=2):
        img_b64 = None
        search_paths = [
            os.path.join(ASSETS_IMAGES_DIR, f"{it.sku}.png"),
            os.path.join(ASSETS_IMAGES_DIR, f"{it.sku}.jpg"),
            os.path.join(ASSETS_IMAGES_DIR, "551000.png")
        ]
        for p in search_paths:
            if os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode("utf-8")
                    break
                except Exception as e:
                    logger.warning(f"Error reading asset {p}: {e}")

        if not img_b64:
            continue

        product_parts.append({
            "inline_data": {"mime_type": "image/png", "data": img_b64}
        })

        color_str = it.color or "standard"
        if "towel" in (it.product_type or "").lower() or (it.system_code or "").startswith("H"):
            default_instructions.append(
                f"- Reference {idx}: {it.name} (SKU {it.sku}, finish: {color_str}). "
                f"Mount flush against the wall near the sink at standard reach height (125 cm from floor). "
                f"Ensure realistic 3D perspective angle matching the wall plane."
            )
        elif "soap" in (it.product_type or "").lower() or (it.system_code or "").startswith("S"):
            default_instructions.append(
                f"- Reference {idx}: {it.name} (SKU {it.sku}, finish: {color_str}). "
                f"Mount on the wall neatly above the vanity countertop next to the washbasin faucet at ergonomic reach height (105 cm from floor)."
            )
        elif "bin" in (it.product_type or "").lower() or (it.system_code or "").startswith("B") or "корзин" in it.name.lower():
            default_instructions.append(
                f"- Reference {idx}: {it.name} (SKU {it.sku}, finish: {color_str}). "
                f"Place neatly on the floor against the wall beneath or adjacent to the hand drying area."
            )
        else:
            default_instructions.append(
                f"- Reference {idx}: {it.name} (SKU {it.sku}, finish: {color_str}). "
                f"Mount flush against the wall in appropriate hygiene functional position."
            )

    if not product_parts:
        return None

    # Incorporate reasoning instructions if available
    reasoned_gen_instructions = (reasoning_plan or {}).get("generation_instructions", "")
    if reasoned_gen_instructions:
        instructions_text = (
            "Smart Spatial Inpainting & Equipment Upgrade Plan:\n" +
            reasoned_gen_instructions + "\n\n" +
            "Reference Product Details:\n" + "\n".join(default_instructions)
        )
    else:
        instructions_text = "Reference Equipment to install:\n" + "\n".join(default_instructions)

    prompt = (
        "You are an expert commercial architectural CGI visualizer for Tork (Essity).\n"
        "Task: Photorealistically edit the commercial washroom interior shown in the first image to mount and place the selected Tork hygiene equipment from the subsequent reference images.\n\n"
        f"{instructions_text}\n\n"
        "Critical Requirements:\n"
        "- If replacing existing equipment (such as an old electric hand dryer, outdated dispenser, soap bottle, or trash bin), ERASE the old item completely and reconstruct the wall tile, reflection, and grout seams flawlessly.\n"
        "- Strictly preserve the client's real room architecture: sink basin, vanity counter, faucets, mirrors, ceiling spotlights, wall tiling, and floor MUST remain identical.\n"
        "- DO NOT paste raw white image rectangles, borders or stickers. Seamlessly composite and render the 3D products as if physically installed in the room.\n"
        "- Match room lighting: cast realistic soft contact drop shadows onto the walls and floor matching ceiling spotlights and wall lights.\n"
        "- Return ONLY the photorealistic final image."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": user_photo_b64}},
                    *product_parts
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"]
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        logger.info(f"Calling Gemini 3.1 Flash Image with {len(product_parts)} product reference images and smart reasoning...")
        with urllib.request.urlopen(req, timeout=90) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            parts = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for p in parts:
                d = p.get("inlineData") or p.get("inline_data")
                if d and d.get("data"):
                    logger.info("Gemini 3.1 Flash Image successfully generated photorealistic fitting!")
                    return d["data"]
    except Exception as e:
        logger.error(f"Gemini 3.1 Flash Image generation error: {e}")
        return None

    return None


@router.post("/composite")
def composite_fitting(req: CompositeRequest):
    """
    Two-stage Smart Replacement & Fitting Pipeline:
    1. Image-to-Reasoning (Gemini 2.5 Flash):
       Analyzes room for existing equipment (dryers, old dispensers, bottles, bins).
       Formulates Smart Replacement (🔄) vs Complement/Add (➕) plan.
    2. Architectural Inpainting (Gemini 3.1 Flash Image):
       Erases old equipment, repairs wall/floor textures, and mounts Tork models in 3D.
    """
    if not req.user_photo_base64:
        raise HTTPException(status_code=400, detail="Missing user_photo_base64")

    # 1. Fetch Selected Items from DB if not provided
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
        items = [KitItem(sku="551000", name="Tork Matic® диспенсер H1")]

    # 2. Stage 1: Image-to-Reasoning Audit
    reasoning_plan = audit_washroom_and_reason_actions(req.user_photo_base64, items)

    # 3. Stage 2: Architectural AI Montage with smart replacement instructions
    ai_result_base64 = call_gemini_photorealistic_fitting(
        req.user_photo_base64,
        items,
        reasoning_plan=reasoning_plan
    )

    # Fallback: if Gemini fails, use user photo
    final_result_base64 = ai_result_base64 or req.user_photo_base64

    # 4. Build comprehensive Telegram caption with Smart Audit & Spec
    caption_lines = [
        "✨ <b>Визуализация санузла готова!</b>\n"
    ]

    # If reasoning provided a telegram audit, include it
    plan_actions = reasoning_plan.get("plan", [])
    replacements = [p for p in plan_actions if p.get("action") == "REPLACE"]
    additions = [p for p in plan_actions if p.get("action") == "ADD"]
    preserved = reasoning_plan.get("preserved_equipment", [])

    if replacements or additions:
        caption_lines.append("🔍 <b>План умной замены и дооснащения:</b>")
        for r in replacements:
            old_name = r.get("replaces_item") or "Старое оборудование"
            caption_lines.append(f"• 🔄 <b>Замена:</b> {old_name} ➔ заменено на арт. <code>{r.get('sku')}</code>")
        for a in additions:
            loc = a.get("target_location") or "Свободная зона"
            caption_lines.append(f"• ➕ <b>Дооснащение:</b> {loc} ➔ установлен арт. <code>{a.get('sku')}</code>")
        if preserved:
            caption_lines.append(f"• 🛡️ <i>Сохранено без изменений: {', '.join(preserved[:2])}</i>")
        caption_lines.append("")

    caption_lines.append("📋 <b>Спецификация смонтированного комплекта:</b>")
    for idx, it in enumerate(items, start=1):
        caption_lines.append(
            f"{idx}. <b>{it.name}</b>\n"
            f"   • Арт: <code>{it.sku}</code> | Сист: <b>{it.system_code or '–'}</b> — {it.count or 1} шт."
        )

    caption_lines.append("\n💡 <i>Монтаж выполнен нейросетью с учетом перспективы, теней и сохранения интерьера.</i>")
    caption = "\n".join(caption_lines)

    return {
        "ok": True,
        "result_image_base64": final_result_base64,
        "caption": caption,
        "mounted_count": len(items),
        "ai_generated": bool(ai_result_base64),
        "audit_plan": reasoning_plan
    }
