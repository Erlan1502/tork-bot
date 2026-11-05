import logging
import base64
import io
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from PIL import Image, ImageFilter

from app.database import get_db_cursor
from app.config import settings
from app.services.presentation_service import (
    compile_manager_presentation,
    compile_commercial_proposal_kz,
    get_default_kp_form_values,
    send_telegram_document,
    answer_telegram_callback
)

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
    token = settings.TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
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


def send_telegram_photo(
    chat_id: int,
    photo_data: Union[bytes, str],
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    # If photo_data is a URL or file_id (short string, not base64)
    if isinstance(photo_data, str) and (photo_data.startswith("http://") or photo_data.startswith("https://") or (len(photo_data) < 200 and not photo_data.startswith("data:"))):
        payload = {
            "chat_id": chat_id,
            "photo": photo_data,
            "parse_mode": "HTML"
        }
        if caption:
            payload["caption"] = caption
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return bool(res.get("ok"))
        except Exception as e:
            logger.error(f"Error sending photo by URL: {e}")
            return False

    # Otherwise decode base64 or use raw bytes
    img_bytes: bytes
    if isinstance(photo_data, str):
        raw_b64 = photo_data
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            logger.error(f"Failed to decode base64 photo for chat {chat_id}: {e}")
            return False
    else:
        img_bytes = photo_data

    boundary = f"----WebKitFormBoundary{os.urandom(16).hex()}"
    body = bytearray()

    # chat_id
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
    body.extend(str(chat_id).encode("utf-8"))
    body.extend(b"\r\n")

    # caption
    if caption:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
        body.extend(caption.encode("utf-8"))
        body.extend(b"\r\n")

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n')
        body.extend(b"HTML\r\n")

    # reply_markup
    if reply_markup:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="reply_markup"\r\n\r\n')
        body.extend(json.dumps(reply_markup, ensure_ascii=False).encode("utf-8"))
        body.extend(b"\r\n")

    # photo binary
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="photo"; filename="restored_fitting.jpg"\r\n')
    body.extend(b"Content-Type: image/jpeg\r\n\r\n")
    body.extend(img_bytes)
    body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    try:
        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("ok"):
                logger.info(f"Successfully sent Telegram photo to chat {chat_id}")
                return True
            else:
                logger.error(f"Telegram API photo error: {res_data}")
                return False
    except Exception as e:
        logger.error(f"Failed to send photo to Telegram chat {chat_id}: {e}")
        return False


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
        '  "generation_instructions": "Clear, precise English instructions for image inpainting detailing what to ERASE and where to MOUNT each Tork SKU. Must explicitly instruct to strictly preserve the exact full-room camera framing and wide-angle borders without zooming in or cropping any surrounding areas (e.g., keep the toilet on the left and full vanity intact)."\n'
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


def get_closest_gemini_aspect_ratio(width: int, height: int) -> str:
    r = width / height
    ratios = {
        "9:16": 9 / 16,     # 0.5625
        "2:3": 2 / 3,       # 0.6667
        "3:4": 3 / 4,       # 0.75
        "4:5": 4 / 5,       # 0.80
        "1:1": 1.0,         # 1.00
        "5:4": 5 / 4,       # 1.25
        "4:3": 4 / 3,       # 1.3333
        "3:2": 3 / 2,       # 1.50
        "16:9": 16 / 9,     # 1.7778
        "21:9": 21 / 9      # 2.3333
    }
    return min(ratios.keys(), key=lambda k: abs(ratios[k] - r))


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

    # 1. Inspect original user photo dimensions to match aspect ratio exactly
    orig_w, orig_h = None, None
    chosen_aspect_ratio = "3:4"
    try:
        raw_b64 = user_photo_b64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        user_img = Image.open(io.BytesIO(base64.b64decode(raw_b64)))
        orig_w, orig_h = user_img.size
        chosen_aspect_ratio = get_closest_gemini_aspect_ratio(orig_w, orig_h)
        logger.info(f"Original user photo size: {orig_w}x{orig_h}, aspect ratio: {round(orig_w/orig_h, 3)}, Gemini target aspect ratio: {chosen_aspect_ratio}")
    except Exception as e:
        logger.warning(f"Could not parse user photo dimensions: {e}")

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
        "CRITICAL REQUIREMENTS:\n"
        "- STRICT CAMERA FRAMING AND FIELD OF VIEW: You MUST strictly preserve 100% of the wide-angle camera view, framing, zoom level, and outer borders of the first image.\n"
        "- DO NOT crop, DO NOT zoom in, DO NOT pan, and DO NOT change the perspective or field of view.\n"
        "- Every element and fixture from the original photo (such as the toilet and wood partition on the far left, the full sink vanity basin, mirror, and marble floor at the bottom) MUST remain completely visible in the exact same positions as in the first image.\n"
        "- If replacing existing equipment (such as an old electric hand dryer, outdated dispenser, soap bottle, or trash bin), ERASE the old item completely and reconstruct the wall tile, reflection, and grout seams flawlessly.\n"
        "- Strictly preserve the client's real room architecture: sink basin, vanity counter, faucets, mirrors, ceiling spotlights, wall tiling, and floor MUST remain identical.\n"
        "- DO NOT paste raw white image rectangles, borders or stickers. Seamlessly composite and render the 3D products as if physically installed in the room.\n"
        "- Match room lighting: cast realistic soft contact drop shadows onto the walls and floor matching ceiling spotlights and wall lights.\n"
        "- Return ONLY the photorealistic final image with the exact same wide-angle framing."
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
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": chosen_aspect_ratio
            }
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        logger.info(f"Calling Gemini 3.1 Flash Image (aspectRatio={chosen_aspect_ratio}) with {len(product_parts)} product reference images and smart reasoning...")
        with urllib.request.urlopen(req, timeout=90) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            parts = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for p in parts:
                d = p.get("inlineData") or p.get("inline_data")
                if d and d.get("data"):
                    gen_b64 = d["data"]
                    if orig_w and orig_h:
                        try:
                            gen_img = Image.open(io.BytesIO(base64.b64decode(gen_b64)))
                            if gen_img.size != (orig_w, orig_h):
                                logger.info(f"Resizing generated image from {gen_img.size} to original photo dimensions ({orig_w}, {orig_h}) to guarantee exact 1:1 match")
                                resized_img = gen_img.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
                                out_buffer = io.BytesIO()
                                resized_img.save(out_buffer, format="JPEG", quality=95)
                                gen_b64 = base64.b64encode(out_buffer.getvalue()).decode("utf-8")
                        except Exception as resize_err:
                            logger.warning(f"Failed to resize generated image: {resize_err}")
                    logger.info("Gemini 3.1 Flash Image successfully generated photorealistic fitting!")
                    return gen_b64
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

    # Persist Before & After images in PostgreSQL user_sessions_leads for presentation compilation
    tg_id = req.tg_user_id or req.chat_id
    if tg_id:
        try:
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_sessions_leads (tg_user_id, before_image_url, last_rendered_image_url, current_step, updated_at)
                    VALUES (%s, %s, %s, 'MONTAGE_COMPLETED', NOW())
                    ON CONFLICT (tg_user_id) DO UPDATE SET
                        before_image_url = EXCLUDED.before_image_url,
                        last_rendered_image_url = EXCLUDED.last_rendered_image_url,
                        current_step = 'MONTAGE_COMPLETED',
                        updated_at = NOW();
                    """,
                    (tg_id, req.user_photo_base64, final_result_base64)
                )
                logger.info(f"Persisted before and after montage images for manager {tg_id}")
        except Exception as e:
            logger.warning(f"Could not persist before/after images in user_sessions_leads: {e}")

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


class RenderPresentationRequest(BaseModel):
    telegram_id: Optional[int] = None
    tg_user_id: Optional[int] = None
    chat_id: Optional[int] = None
    system_code: Optional[str] = None
    segment: Optional[str] = None
    before_image: Optional[str] = None
    after_image: Optional[str] = None
    send_to_telegram: Optional[bool] = False
    callback_query_id: Optional[str] = None
    format: Optional[str] = "pdf"  # "pdf" or "json"


@router.post("/render-presentation")
def render_presentation(req: RenderPresentationRequest, format: Optional[str] = None):
    """
    Production Presentation Generator Endpoint for Tork Kazakhstan (Phase 2):
    - Accepts manager telegram_id.
    - Loads client washroom photo (Before) & Gemini montage (After) from PostgreSQL user_sessions_leads.
    - Loads selected system & SKU from user_sessions_leads.
    - Injects verified Essity proof facts & metrics (percentages, seconds, doses) via get_system_arguments().
    - Compiles strictly 1-page A4 PDF via Gotenberg Chromium (~0.4s, 0 AI tokens).
    - If send_to_telegram=True: delivers PDF document directly to manager chat in Telegram.
    - Otherwise returns PDF binary or JSON metadata with file URL.
    """
    tg_id = req.telegram_id or req.tg_user_id or req.chat_id
    if not tg_id:
        raise HTTPException(status_code=400, detail="telegram_id is required")

    try:
        pdf_bytes, filename, meta = compile_manager_presentation(
            telegram_id=tg_id,
            system_code_override=req.system_code,
            segment_override=req.segment,
            before_image_override=req.before_image,
            after_image_override=req.after_image
        )
    except Exception as e:
        logger.error(f"Failed to compile presentation for manager {tg_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compile presentation: {e}")

    # If requested to send directly to Telegram chat
    if req.send_to_telegram:
        target_chat_id = req.chat_id or tg_id
        caption = (
            f"📊 <b>Презентация решения Tork готова!</b>\n\n"
            f"• <b>Система:</b> {meta['system_name']} ({meta['system_code']})\n"
            f"• <b>Артикул:</b> <code>{meta['sku']}</code>\n\n"
            f"📄 <i>Одностраничное коммерческое предложение для клиента с расчетом эффективности, окупаемости и визуализацией До/После.</i>"
        )
        sent = send_telegram_document(target_chat_id, pdf_bytes, filename, caption)
        if req.callback_query_id:
            answer_telegram_callback(req.callback_query_id, text="Презентация сформирована и отправлена в чат!")

        return {
            "ok": True,
            "status": "sent" if sent else "telegram_send_failed",
            "chat_id": target_chat_id,
            "filename": filename,
            "system_code": meta["system_code"],
            "system_name": meta["system_name"],
            "sku": meta["sku"],
            "file_url": f"/presentations/{filename}",
            "size_bytes": len(pdf_bytes)
        }

    # If JSON response requested
    req_format = (format or req.format or "pdf").lower()
    if req_format == "json":
        return {
            "ok": True,
            "filename": filename,
            "system_code": meta["system_code"],
            "system_name": meta["system_name"],
            "sku": meta["sku"],
            "file_url": f"/presentations/{filename}",
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "size_bytes": len(pdf_bytes)
        }

    # Default: Return PDF binary with attachment headers
    quoted_filename = urllib.parse.quote(filename)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
            "X-Filename": quoted_filename,
            "X-System-Code": meta["system_code"],
            "X-SKU": meta["sku"]
        }
    )


@router.get("/render-presentation")
def render_presentation_get(
    telegram_id: int,
    system_code: Optional[str] = None,
    segment: Optional[str] = None,
    format: Optional[str] = "pdf",
    send_to_telegram: Optional[bool] = False
):
    """
    Convenience GET endpoint to render / test presentation directly in browser or Swagger UI.
    """
    req = RenderPresentationRequest(
        telegram_id=telegram_id,
        system_code=system_code,
        segment=segment,
        send_to_telegram=send_to_telegram,
        format=format
    )
    return render_presentation(req, format=format)


# ==============================================================================
# PHASE 4: FULL COMMERCIAL PROPOSAL GENERATOR V2 (KAZAKHSTAN 5-PAGE KP)
# ==============================================================================

class GenerateKPRequest(BaseModel):
    telegram_id: Optional[int] = None
    tg_user_id: Optional[int] = None
    chat_id: Optional[int] = None
    company_name: Optional[str] = None
    client_facility: Optional[str] = None
    client_city: Optional[str] = "г. Астана, Казахстан"
    manager_name: Optional[str] = None
    manager_phone: Optional[str] = None
    manager_tg: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    hero_image: Optional[str] = None
    send_to_telegram: Optional[bool] = False
    callback_query_id: Optional[str] = None
    format: Optional[str] = "pdf"


@router.get("/form-defaults")
def get_form_defaults(telegram_id: Optional[int] = None):
    """
    Returns prefilled form values for Kazakhstan KP generator (5-page PDF):
    - Manager full name from allowed_managers
    - Manager phone from allowed_managers / session
    - City (default: г. Астана, Казахстан)
    - Client facility & company if previously recorded
    """
    tg_id = telegram_id or 5699064827
    defaults = get_default_kp_form_values(tg_id)
    return {
        "ok": True,
        "defaults": defaults
    }


@router.post("/generate-kp")
def generate_kp(req: GenerateKPRequest, format: Optional[str] = None):
    """
    Commercial Proposal Generator for Kazakhstan (Phase 4):
    - Strict 5-page A4 document matching reference 'КП 1.pdf'
    - Highlighting 16% VAT (актуальная ставка РК)
    - 50% advance / 50% remainder payment condition
    - Visual photomontage embedded on Page 1 (hero image)
    - Detailed equipment distribution by rooms/floors on Page 3
    - Tork system advantages & 40% savings infographics on Page 4
    - 6-step implementation workflow & manager contacts on Page 5
    - If send_to_telegram=True: delivers PDF document directly to manager chat.
    """
    tg_id = req.telegram_id or req.tg_user_id or req.chat_id or 5699064827

    from app.services.presentation_service import get_manager_presentation_data
    session_data = get_manager_presentation_data(tg_id)

    comp_name = (req.company_name or "").strip() or session_data.get("company_name") or "ТОО «Заказчик»"
    facility = (req.client_facility or "").strip() or session_data.get("client_facility") or "Гостиничный комплекс, 5 этажей, 42 санузла"
    city = (req.client_city or "").strip() or session_data.get("client_city") or "г. Астана, Казахстан"

    try:
        pdf_bytes, filename, meta = compile_commercial_proposal_kz(
            telegram_id=tg_id,
            company_name=comp_name,
            client_facility=facility,
            client_city=city,
            manager_name=req.manager_name,
            manager_phone=req.manager_phone,
            manager_tg=req.manager_tg,
            items_override=req.items,
            hero_image_override=req.hero_image
        )
    except Exception as e:
        logger.error(f"Failed to compile commercial proposal for manager {tg_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compile commercial proposal: {e}")

    # Persist updated company_name, facility, and selected_bundle if provided
    try:
        with get_db_cursor() as cur:
            if req.items and len(req.items) > 0:
                primary_sku = str(req.items[0].get("sku", "551000")).strip()
                cur.execute(
                    """
                    UPDATE user_sessions_leads
                    SET company_name = %s,
                        client_facility = %s,
                        client_city = %s,
                        selected_sku = %s,
                        selected_bundle = %s::jsonb,
                        updated_at = NOW()
                    WHERE tg_user_id = %s;
                    """,
                    (comp_name, facility, city, primary_sku, json.dumps(req.items, ensure_ascii=False), tg_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE user_sessions_leads
                    SET company_name = %s,
                        client_facility = %s,
                        client_city = %s,
                        updated_at = NOW()
                    WHERE tg_user_id = %s;
                    """,
                    (comp_name, facility, city, tg_id)
                )
    except Exception as e:
        logger.warning(f"Could not update session metadata for tg_id {tg_id}: {e}")

    if req.send_to_telegram:
        target_chat_id = req.chat_id or tg_id
        caption = (
            f"🏢 <b>Коммерческое предложение Tork готово!</b>\n\n"
            f"• <b>Клиент:</b> {meta['client_name']}\n"
            f"• <b>Объект:</b> {meta['client_facility']}\n"
            f"• <b>Сумма:</b> {int(round(meta['total_amount'])):,} ₸ (НДС 16%)\n"
            f"• <b>Предоплата 50%:</b> {int(round(meta['prepayment_amount'])):,} ₸\n"
            f"• <b>Монтаж:</b> 0 ₸ (Бесплатно)\n\n"
            f"📄 <i>4 страницы А4: титул с фотомонтажом, спецификация с ценами и расходниками, инфографика окупаемости и условия договора.</i>"
        ).replace(",", " ")
        sent = send_telegram_document(target_chat_id, pdf_bytes, filename, caption)
        if req.callback_query_id:
            answer_telegram_callback(req.callback_query_id, text="Коммерческое предложение успешно сформировано и отправлено в чат!")

        return {
            "ok": True,
            "status": "sent" if sent else "telegram_send_failed",
            "chat_id": target_chat_id,
            "filename": filename,
            "client_name": meta["client_name"],
            "total_amount": meta["total_amount"],
            "prepayment_amount": meta["prepayment_amount"],
            "file_url": f"/presentations/{filename}",
            "size_bytes": len(pdf_bytes)
        }

    req_format = (format or req.format or "pdf").lower()
    if req_format == "json":
        return {
            "ok": True,
            "filename": filename,
            "client_name": meta["client_name"],
            "total_amount": meta["total_amount"],
            "prepayment_amount": meta["prepayment_amount"],
            "file_url": f"/presentations/{filename}",
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "size_bytes": len(pdf_bytes)
        }

    quoted_filename = urllib.parse.quote(filename)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
            "X-Filename": quoted_filename,
            "X-Client-Name": urllib.parse.quote(meta["client_name"]),
            "X-Total-Amount": str(meta["total_amount"])
        }
    )


@router.get("/generate-kp")
def generate_kp_get(
    company_name: str,
    client_facility: str,
    telegram_id: Optional[int] = 5699064827,
    client_city: Optional[str] = "г. Астана, Казахстан",
    manager_name: Optional[str] = None,
    manager_phone: Optional[str] = None,
    format: Optional[str] = "pdf",
    send_to_telegram: Optional[bool] = False
):
    """
    Convenience GET endpoint to generate Kazakhstan KP directly in browser.
    """
    req = GenerateKPRequest(
        telegram_id=telegram_id,
        company_name=company_name,
        client_facility=client_facility,
        client_city=client_city,
        manager_name=manager_name,
        manager_phone=manager_phone,
        send_to_telegram=send_to_telegram,
        format=format
    )
    return generate_kp(req, format=format)


# ==============================================================================
# PHASE 3: INTERACTIVE SCENARIOS & MISCLICK PROTECTION (UNDO ROLLBACK)
# ==============================================================================

class ChangeDispenserRequest(BaseModel):
    telegram_id: Optional[int] = None
    tg_user_id: Optional[int] = None
    chat_id: Optional[int] = None
    callback_query_id: Optional[str] = None
    send_to_telegram: Optional[bool] = False


class RestoreMontageRequest(BaseModel):
    telegram_id: Optional[int] = None
    tg_user_id: Optional[int] = None
    chat_id: Optional[int] = None
    callback_query_id: Optional[str] = None
    send_to_telegram: Optional[bool] = False


@router.post("/change-dispenser")
def change_dispenser(req: ChangeDispenserRequest):
    """
    Phase 3: Manager triggers '🔄 Выбрать другой диспенсер'.
    1. Archives current montage state (selected_sku, selected_bundle, before_image_url, last_rendered_image_url)
       into user_sessions_leads.previous_montage_state.
    2. CRITICAL: Current rendered image and selected SKU are NOT deleted from the database.
    3. Updates session current_step to 'SELECTING_DISPENSER'.
    4. If send_to_telegram=True:
       Answers callback query and sends undo warning message:
       «Вы вернулись к каталогу для выбора другого оборудования.
       ⚠️ Нажали случайно? Нажмите кнопку ниже, чтобы вернуть текущий монтаж.»
       With keyboard: [ ↩️ Вернуть предыдущий монтаж ] | [ 🛍 Открыть каталог ]
    """
    tg_id = req.telegram_id or req.tg_user_id or req.chat_id
    if not tg_id:
        raise HTTPException(status_code=400, detail="telegram_id is required")

    target_chat_id = req.chat_id or tg_id

    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT tg_user_id, selected_sku, selected_bundle, before_image_url, 
                       last_rendered_image_url, previous_montage_state
                FROM user_sessions_leads
                WHERE tg_user_id = %s;
                """,
                (tg_id,)
            )
            row = cur.fetchone()

            if not row:
                cur.execute(
                    """
                    INSERT INTO user_sessions_leads (tg_user_id, selected_sku, current_step, updated_at)
                    VALUES (%s, '551000', 'SELECTING_DISPENSER', NOW())
                    RETURNING tg_user_id, selected_sku, selected_bundle, before_image_url, last_rendered_image_url, previous_montage_state;
                    """,
                    (tg_id,)
                )
                row = cur.fetchone()

            current_sku = row.get("selected_sku") or "551000"
            archive_state = {
                "selected_sku": current_sku,
                "selected_bundle": row.get("selected_bundle"),
                "before_image_url": row.get("before_image_url"),
                "last_rendered_image_url": row.get("last_rendered_image_url"),
                "archived_at": datetime.utcnow().isoformat()
            }

            cur.execute(
                """
                UPDATE user_sessions_leads
                SET previous_montage_state = %s::jsonb,
                    current_step = 'SELECTING_DISPENSER',
                    updated_at = NOW()
                WHERE tg_user_id = %s;
                """,
                (json.dumps(archive_state, ensure_ascii=False), tg_id)
            )
            logger.info(f"Archived montage state for manager {tg_id}: SKU {current_sku}")
    except Exception as e:
        logger.error(f"Error archiving montage state for {tg_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if req.callback_query_id:
        answer_telegram_callback(req.callback_query_id, text="Вы перешли к выбору оборудования")

    webhook_base = (settings.WEBHOOK_URL or os.getenv("WEBHOOK_URL", "http://localhost:8088")).rstrip("/")
    webapp_url = f"{webhook_base}/app/index.html"

    message_text = (
        "Вы вернулись к каталогу для выбора другого оборудования.\n"
        "⚠️ Нажали случайно? Нажмите кнопку ниже, чтобы вернуть текущий монтаж."
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "↩️ Вернуть предыдущий монтаж",
                    "callback_data": "restore_previous_montage"
                }
            ],
            [
                {
                    "text": "🛍 Открыть каталог",
                    "web_app": {
                        "url": webapp_url
                    }
                }
            ]
        ]
    }

    if req.send_to_telegram:
        send_telegram_message(target_chat_id, message_text, reply_markup=reply_markup)

    return {
        "ok": True,
        "status": "archived",
        "telegram_id": tg_id,
        "current_step": "SELECTING_DISPENSER",
        "previous_montage_state": archive_state,
        "message_text": message_text,
        "reply_markup": reply_markup
    }


@router.get("/change-dispenser")
def change_dispenser_get(telegram_id: int, send_to_telegram: Optional[bool] = False):
    """Convenience GET endpoint to trigger change-dispenser."""
    return change_dispenser(ChangeDispenserRequest(telegram_id=telegram_id, send_to_telegram=send_to_telegram))


@router.post("/restore-montage")
def restore_montage(req: RestoreMontageRequest):
    """
    Phase 3: Accidental misclick protection & Instant State Rollback ('↩️ Вернуть предыдущий монтаж').
    1. Loads archived montage state from user_sessions_leads.previous_montage_state.
    2. Restores selected_sku, selected_bundle, last_rendered_image_url into active session.
    3. Updates current_step to 'MONTAGE_RESTORED'.
    4. Instantly sends restored montage photo back with original buttons:
       [ 📊 Скачать презентацию (PDF) ]
       [ 🔄 Выбрать другой диспенсер ]
    5. ZERO Gemini token consumption and zero re-computation.
    """
    tg_id = req.telegram_id or req.tg_user_id or req.chat_id
    if not tg_id:
        raise HTTPException(status_code=400, detail="telegram_id is required")

    target_chat_id = req.chat_id or tg_id

    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT tg_user_id, selected_sku, selected_bundle, before_image_url, 
                       last_rendered_image_url, previous_montage_state
                FROM user_sessions_leads
                WHERE tg_user_id = %s;
                """,
                (tg_id,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Сессия пользователя не найдена")

            prev = row.get("previous_montage_state")
            if not prev and not row.get("last_rendered_image_url"):
                raise HTTPException(status_code=400, detail="Нет сохраненного предыдущего монтажа для возврата")

            prev_dict = prev if isinstance(prev, dict) else (json.loads(prev) if prev else {})
            restored_sku = prev_dict.get("selected_sku") or row.get("selected_sku") or "551000"
            restored_bundle = prev_dict.get("selected_bundle") or row.get("selected_bundle")
            restored_img = prev_dict.get("last_rendered_image_url") or row.get("last_rendered_image_url")
            restored_before = prev_dict.get("before_image_url") or row.get("before_image_url")

            cur.execute(
                """
                UPDATE user_sessions_leads
                SET selected_sku = %s,
                    selected_bundle = %s,
                    last_rendered_image_url = %s,
                    before_image_url = %s,
                    current_step = 'MONTAGE_RESTORED',
                    updated_at = NOW()
                WHERE tg_user_id = %s;
                """,
                (
                    restored_sku,
                    json.dumps(restored_bundle, ensure_ascii=False) if restored_bundle else None,
                    restored_img,
                    restored_before,
                    tg_id
                )
            )

            # Fetch product details for restored caption
            cur.execute(
                "SELECT name, system_code, color FROM products WHERE sku = %s LIMIT 1;",
                (restored_sku,)
            )
            prod = cur.fetchone()
            prod_name = prod["name"] if prod else f"Диспенсер Tork (арт. {restored_sku})"
            prod_system = prod["system_code"] if prod else "H1"
            prod_color = prod["color"] if prod else "white"

            color_map = {
                "white": "Белый",
                "black": "Черный",
                "stainless_steel": "Нержавеющая сталь",
                "none": "Стандарт"
            }
            color_ru = color_map.get((prod_color or "").lower(), prod_color or "Белый")

            logger.info(f"Restored previous montage for manager {tg_id}: SKU {restored_sku} (0 tokens consumed)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring montage for {tg_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if req.callback_query_id:
        answer_telegram_callback(req.callback_query_id, text="Предыдущий монтаж успешно возвращен!")

    caption = (
        f"✨ <b>Визуализация санузла возвращена!</b>\n\n"
        f"• Диспенсер: <b>{prod_name}</b>\n"
        f"• Артикул: <code>{restored_sku}</code>\n"
        f"• Система: <b>{prod_system}</b> ({color_ru})\n\n"
        f"<i>Монтаж восстановлен из сессии без повторного расхода токенов.</i>"
    )

    result_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📄 Создать КП (PDF)",
                    "callback_data": "create_kp"
                }
            ],
            [
                {
                    "text": "📊 Скачать презентацию (PDF)",
                    "callback_data": "download_presentation"
                }
            ],
            [
                {
                    "text": "🔄 Выбрать другой диспенсер",
                    "callback_data": "change_dispenser"
                }
            ]
        ]
    }

    if req.send_to_telegram and restored_img:
        send_telegram_photo(target_chat_id, restored_img, caption=caption, reply_markup=result_keyboard)

    return {
        "ok": True,
        "status": "restored",
        "telegram_id": tg_id,
        "restored_sku": restored_sku,
        "system_code": prod_system,
        "has_rendered_image": bool(restored_img),
        "tokens_consumed": 0,
        "ai_recomputed": False,
        "current_step": "MONTAGE_RESTORED",
        "caption": caption,
        "reply_markup": result_keyboard
    }


@router.get("/restore-montage")
def restore_montage_get(telegram_id: int, send_to_telegram: Optional[bool] = False):
    """Convenience GET endpoint to trigger restore-montage."""
    return restore_montage(RestoreMontageRequest(telegram_id=telegram_id, send_to_telegram=send_to_telegram))


