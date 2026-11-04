"""
Presentation Generator Service for Tork Kazakhstan.
Compiles single-page A4 commercial presentations for managers with Essity certified metrics,
client room photo (Before) and Gemini photorealistic montage (After) via Gotenberg.
"""

import os
import io
import uuid
import json
import base64
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple, Union

import jinja2

from app.config import settings
from app.database import get_db_cursor
from app.services.tork_arguments import get_system_arguments

logger = logging.getLogger(__name__)

# Template paths
TEMPLATE_SEARCH_PATHS = [
    os.path.join(settings.TEMPLATE_DIR, "presentation_template.html"),
    "/app/templates/presentation_template.html",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../templates/presentation_template.html")),
    os.path.abspath(os.path.join(os.getcwd(), "templates/presentation_template.html"))
]

KP_TEMPLATE_SEARCH_PATHS = [
    os.path.join(settings.TEMPLATE_DIR, "kp_kz_template.html"),
    "/app/templates/kp_kz_template.html",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../templates/kp_kz_template.html")),
    os.path.abspath(os.path.join(os.getcwd(), "templates/kp_kz_template.html"))
]

# Assets & Generated files paths
ASSETS_SEARCH_DIRS = [
    settings.ASSETS_DIR,
    "/app/assets",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../assets")),
    os.path.abspath(os.path.join(os.getcwd(), "assets")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
    os.path.abspath(os.getcwd())
]

OUTPUT_SEARCH_DIRS = [
    settings.GENERATED_PRESENTATIONS_DIR,
    "/app/generated_presentations",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../generated_presentations")),
    os.path.abspath(os.path.join(os.getcwd(), "generated_presentations"))
]


def resolve_existing_path(filename: str, directories: list) -> Optional[str]:
    for d in directories:
        if d and os.path.exists(d):
            p = os.path.join(d, filename)
            if os.path.isfile(p):
                return p
            p_img = os.path.join(d, "images", filename)
            if os.path.isfile(p_img):
                return p_img
            p_img_png = os.path.join(d, "images", f"{filename}.png")
            if os.path.isfile(p_img_png):
                return p_img_png
            p_sample = os.path.join(d, "sample_fittings", filename)
            if os.path.isfile(p_sample):
                return p_sample
    # Check workspace root directly
    root_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../", filename))
    if os.path.isfile(root_file):
        return root_file
    return None


def get_template_html() -> str:
    for path in TEMPLATE_SEARCH_PATHS:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to read template at {path}: {e}")
    raise FileNotFoundError("presentation_template.html not found in search paths")


def get_kp_template_html() -> str:
    for path in KP_TEMPLATE_SEARCH_PATHS:
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to read template at {path}: {e}")
    raise FileNotFoundError("kp_kz_template.html not found in search paths")


def image_to_data_uri(img_source: Optional[str], default_rel_path: str = "sample_fittings/pres_sample_0.png") -> str:
    """
    Normalizes any image source (data URI, base64, URL, local path, or fallback)
    into a valid Data URI string (data:image/...;base64,...) for embedding in HTML.
    """
    if not img_source:
        return _fallback_data_uri(default_rel_path)

    img_source = img_source.strip()

    # 1. Already a Data URI
    if img_source.startswith("data:image/"):
        return img_source

    # 2. Raw base64 string
    # Check if string does not contain path separators or http and is long enough
    if len(img_source) > 80 and not img_source.startswith("http") and not os.path.exists(img_source):
        clean_b64 = img_source.replace("\n", "").replace("\r", "")
        # Heuristic detection of png vs jpeg/webp
        if clean_b64.startswith("iVBOR"):
            mime = "image/png"
        elif clean_b64.startswith("/9j/"):
            mime = "image/jpeg"
        else:
            mime = "image/jpeg"
        return f"data:{mime};base64,{clean_b64}"

    # 3. HTTP / HTTPS URL
    if img_source.startswith("http://") or img_source.startswith("https://"):
        try:
            req = urllib.request.Request(img_source, headers={"User-Agent": "TorkBot/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read()
                content_type = resp.headers.get_content_type() or "image/jpeg"
                b64 = base64.b64encode(data).decode("utf-8")
                return f"data:{content_type};base64,{b64}"
        except Exception as e:
            logger.warning(f"Could not download image from URL '{img_source}': {e}")
            return _fallback_data_uri(default_rel_path)

    # 4. Local File Path
    if os.path.isfile(img_source):
        try:
            with open(img_source, "rb") as f:
                data = f.read()
            ext = os.path.splitext(img_source)[1].lstrip(".").lower()
            mime = "image/png" if ext == "png" else "image/jpeg"
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.warning(f"Could not read image file '{img_source}': {e}")
            return _fallback_data_uri(default_rel_path)

    # 5. Check if it's a relative path in assets
    resolved = resolve_existing_path(img_source, ASSETS_SEARCH_DIRS)
    if resolved:
        try:
            with open(resolved, "rb") as f:
                data = f.read()
            ext = os.path.splitext(resolved)[1].lstrip(".").lower()
            mime = "image/png" if ext == "png" else "image/jpeg"
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.warning(f"Could not read resolved image asset '{resolved}': {e}")

    return _fallback_data_uri(default_rel_path)


def _fallback_data_uri(default_rel_path: str) -> str:
    resolved = resolve_existing_path(default_rel_path, ASSETS_SEARCH_DIRS)
    if not resolved:
        # Try direct search without sample_fittings
        basename = os.path.basename(default_rel_path)
        resolved = resolve_existing_path(basename, ASSETS_SEARCH_DIRS)

    if resolved and os.path.isfile(resolved):
        try:
            with open(resolved, "rb") as f:
                data = f.read()
            ext = os.path.splitext(resolved)[1].lstrip(".").lower()
            mime = "image/png" if ext == "png" else "image/jpeg"
            b64 = base64.b64encode(data).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.warning(f"Error reading fallback image '{resolved}': {e}")

    # Fallback 1x1 transparent png if completely absent
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def call_gotenberg_html_to_pdf(html_content: str) -> bytes:
    """
    Sends compiled HTML with inline base64 images to Gotenberg Chromium endpoint.
    Gotenberg returns the binary PDF strictly matching the CSS A4 @page (1 page).
    """
    base_gotenberg = os.getenv("GOTENBERG_URL", settings.GOTENBERG_URL or "http://gotenberg:3000")
    if not base_gotenberg.endswith("/forms/chromium/convert/html"):
        gotenberg_url = base_gotenberg.rstrip("/") + "/forms/chromium/convert/html"
    else:
        gotenberg_url = base_gotenberg

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()

    # index.html file
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="files"; filename="index.html"\r\nContent-Type: text/html; charset=utf-8\r\n\r\n')
    body.extend(html_content.encode("utf-8"))
    body.extend(b"\r\n")

    # Options
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="preferCssPageSize"\r\n\r\ntrue\r\n')

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(b'Content-Disposition: form-data; name="printBackground"\r\n\r\ntrue\r\n')

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    # Try container URL, fallback to localhost if developing on host
    urls_to_try = [gotenberg_url]
    if "gotenberg:3000" in gotenberg_url:
        urls_to_try.append(gotenberg_url.replace("gotenberg:3000", "localhost:3000"))

    last_error = None
    for url in urls_to_try:
        try:
            req = urllib.request.Request(
                url,
                data=bytes(body),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                pdf_bytes = resp.read()
                logger.info(f"Gotenberg compiled PDF successfully via {url} ({len(pdf_bytes)} bytes)")
                return pdf_bytes
        except Exception as e:
            last_error = e
            logger.warning(f"Gotenberg call failed for {url}: {e}")

    raise RuntimeError(f"Failed to compile PDF via Gotenberg: {last_error}")


def compile_presentation(
    system_code: str,
    segment: str,
    before_image_data_uri: str,
    after_image_data_uri: str
) -> bytes:
    """
    Renders presentation_template.html with Jinja2 and converts to PDF via Gotenberg.
    """
    template_str = get_template_html()
    sys_info = get_system_arguments(system_code, segment)

    jinja_env = jinja2.Environment(autoescape=True)
    tpl = jinja_env.from_string(template_str)

    context = {
        "system_name": sys_info["system_name"],
        "tagline": sys_info["tagline"],
        "solution_summary": sys_info["solution_summary"],
        "arguments": sys_info["arguments"],
        "before_image_data_uri": before_image_data_uri,
        "after_image_data_uri": after_image_data_uri
    }

    html = tpl.render(**context)
    return call_gotenberg_html_to_pdf(html)


def get_manager_presentation_data(telegram_id: int) -> Dict[str, Any]:
    """
    Queries PostgreSQL (user_sessions_leads) for the manager's active fitting session.
    """
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT tg_user_id, client_name, company_name, business_segment,
                   selected_sku, selected_bundle, before_image_url, last_rendered_image_url
            FROM user_sessions_leads
            WHERE tg_user_id = %s;
            """,
            (telegram_id,)
        )
        row = cur.fetchone()
        if not row:
            return {}
        return dict(row)


def resolve_system_and_sku(
    session_data: Dict[str, Any],
    system_code_override: Optional[str] = None
) -> Tuple[str, str]:
    """
    Determines system code and product SKU from session or overrides.
    """
    sku = None
    system_code = system_code_override

    # 1. From selected_bundle
    bundle = session_data.get("selected_bundle")
    if bundle:
        if isinstance(bundle, list) and len(bundle) > 0:
            primary = bundle[0]
            sku = primary.get("sku")
            if not system_code:
                system_code = primary.get("system_code")
        elif isinstance(bundle, dict):
            sku = bundle.get("sku")
            if not system_code:
                system_code = bundle.get("system_code")

    # 2. From selected_sku
    if not sku:
        sku = session_data.get("selected_sku")

    # 3. Fallback SKU
    if not sku:
        sku = "551000"

    # 4. If system_code still missing, query products table
    if not system_code and sku:
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT system_code FROM products WHERE sku = %s LIMIT 1;", (sku,))
                prod = cur.fetchone()
                if prod and prod.get("system_code"):
                    system_code = prod["system_code"]
        except Exception as e:
            logger.warning(f"Error querying system_code for SKU {sku}: {e}")

    if not system_code:
        system_code = "H1"

    return system_code.strip().upper(), sku.strip()


def compile_manager_presentation(
    telegram_id: int,
    system_code_override: Optional[str] = None,
    segment_override: Optional[str] = None,
    before_image_override: Optional[str] = None,
    after_image_override: Optional[str] = None
) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Full pipeline to compile manager presentation:
    1. Fetch session from DB.
    2. Determine SKU & System (H1, H2, S4, T8, B1, etc.).
    3. Determine segment & get facts from get_system_arguments().
    4. Normalize Before and After photos into Data URIs.
    5. Render and compile 1-page PDF via Gotenberg (~0.4 sec).
    6. Returns (pdf_bytes, filename, metadata).
    """
    session_data = get_manager_presentation_data(telegram_id)

    system_code, sku = resolve_system_and_sku(session_data, system_code_override)
    segment = segment_override or session_data.get("business_segment") or "general"

    sys_info = get_system_arguments(system_code, segment)

    # Determine image sources
    before_source = before_image_override or session_data.get("before_image_url")
    after_source = after_image_override or session_data.get("last_rendered_image_url")

    before_data_uri = image_to_data_uri(before_source, "sample_fittings/pres_sample_0.png")
    after_data_uri = image_to_data_uri(after_source, "sample_fittings/pres_sample_1.png")

    # Compile PDF
    pdf_bytes = compile_presentation(
        system_code=system_code,
        segment=segment,
        before_image_data_uri=before_data_uri,
        after_image_data_uri=after_data_uri
    )

    filename = f"Презентация_Tork_{system_code}_{sku}.pdf"

    # Save to generated_presentations dir if available
    try:
        out_dir = None
        for d in OUTPUT_SEARCH_DIRS:
            if d:
                os.makedirs(d, exist_ok=True)
                out_dir = d
                break
        if out_dir:
            file_path = os.path.join(out_dir, filename)
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"Saved generated presentation to {file_path}")
    except Exception as e:
        logger.warning(f"Failed to persist presentation copy to disk: {e}")

    metadata = {
        "system_code": system_code,
        "system_name": sys_info["system_name"],
        "category": sys_info["category"],
        "sku": sku,
        "segment": segment,
        "tagline": sys_info["tagline"],
        "filename": filename,
        "size_bytes": len(pdf_bytes)
    }

    return pdf_bytes, filename, metadata


def send_telegram_document(
    chat_id: int,
    document_bytes: bytes,
    filename: str,
    caption: str = ""
) -> bool:
    """
    Sends binary PDF document to Telegram chat using official Telegram Bot API sendDocument.
    """
    token = settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        logger.warning(f"TELEGRAM_BOT_TOKEN or chat_id ({chat_id}) missing, cannot send document")
        return False

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
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

    # document binary
    clean_filename = filename.replace('"', '').replace('\n', '')
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="document"; filename="{clean_filename}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: application/pdf\r\n\r\n")
    body.extend(document_bytes)
    body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    try:
        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("ok"):
                logger.info(f"Successfully sent presentation '{filename}' to Telegram chat {chat_id}")
                return True
            else:
                logger.error(f"Telegram API error: {res_data}")
                return False
    except Exception as e:
        logger.error(f"Failed to send document to Telegram chat {chat_id}: {e}")
        return False


def answer_telegram_callback(callback_query_id: str, text: Optional[str] = None):
    token = settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or not callback_query_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        logger.warning(f"Error answering callback query {callback_query_id}: {e}")


# ==============================================================================
# PHASE 4: FULL COMMERCIAL PROPOSAL GENERATOR V2 (KAZAKHSTAN 5-PAGE KP)
# ==============================================================================

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}


def get_manager_profile_by_tg_id(telegram_id: int) -> Dict[str, Any]:
    """
    Looks up manager in allowed_managers table by telegram_id.
    """
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT telegram_id, full_name, username, phone, role, is_active
                FROM allowed_managers
                WHERE telegram_id = %s;
                """,
                (telegram_id,)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.warning(f"Failed to lookup manager in allowed_managers for tg_id {telegram_id}: {e}")
    return {}


def get_default_kp_form_values(telegram_id: int) -> Dict[str, Any]:
    """
    Provides prefilled data for the WebApp modal / bot form:
    - Manager name (from allowed_managers)
    - Manager phone (from allowed_managers or session)
    - City (default: г. Астана, Казахстан)
    - Client company & facility if previously set in session
    """
    manager = get_manager_profile_by_tg_id(telegram_id)
    session = get_manager_presentation_data(telegram_id)

    manager_name = manager.get("full_name") or session.get("client_name") or "Ерлан Кубесов"
    manager_phone = manager.get("phone") or session.get("phone") or "+7 (777) 777-77-77"
    username = manager.get("username") or session.get("tg_username") or "erlan_tork_kz"
    manager_tg = f"@{username.lstrip('@')}"

    return {
        "telegram_id": telegram_id,
        "manager_name": manager_name,
        "manager_phone": manager_phone,
        "manager_tg": manager_tg,
        "client_city": session.get("client_city") or "г. Астана, Казахстан",
        "company_name": session.get("company_name") or "",
        "client_facility": session.get("client_facility") or "Гостиничный комплекс, 5 этажей, 42 санузла",
        "has_montage_image": bool(session.get("last_rendered_image_url")),
        "selected_sku": session.get("selected_sku") or "551000"
    }


def build_room_distribution(
    dispenser_items: List[Dict[str, Any]],
    client_facility: str
) -> List[Dict[str, Any]]:
    """
    Distributes dispensers deterministically across 3 blocks / 6 room types.
    Ensures that sum of counts for each SKU strictly equals item["count"].
    """
    room_specs = [
        {"block": "БЛОК 1 · 1 ЭТАЖ (Входная группа и гостевые зоны)", "room_name": "Санузлы посетителей и фойе (М/Ж)", "weight": 0.35},
        {"block": "БЛОК 1 · 1 ЭТАЖ (Входная группа и гостевые зоны)", "room_name": "Служебный санузел персонала входной зоны", "weight": 0.15},
        {"block": "БЛОК 1 · 2–3 ЭТАЖИ (Основные рабочие зоны объекта)", "room_name": "Общественные санузлы этажей (М/Ж)", "weight": 0.25},
        {"block": "БЛОК 1 · 2–3 ЭТАЖИ (Основные рабочие зоны объекта)", "room_name": "Специализированные помещения / кабинеты", "weight": 0.10},
        {"block": "БЛОК 2 · 4–5 ЭТАЖИ (Администрация и VIP-сектор)", "room_name": "VIP-санузлы руководства и делегаций", "weight": 0.10},
        {"block": "БЛОК 2 · 4–5 ЭТАЖИ (Администрация и VIP-сектор)", "room_name": "Сервисные санузлы и комната клининга", "weight": 0.05},
    ]

    allocated_rooms = []
    for r in room_specs:
        allocated_rooms.append({
            "block": r["block"],
            "room_name": r["room_name"],
            "counts": {},
            "total_units": 0,
            "subtotal": 0.0
        })

    for item in dispenser_items:
        sku = item["sku"]
        total_qty = int(item["count"])
        price = float(item["price"])

        remaining = total_qty
        for i, r in enumerate(room_specs):
            if i == len(room_specs) - 1:
                take = remaining
            else:
                take = int(round(total_qty * r["weight"]))
                if take > remaining:
                    take = remaining
            allocated_rooms[i]["counts"][sku] = take
            allocated_rooms[i]["total_units"] += take
            allocated_rooms[i]["subtotal"] += take * price
            remaining -= take

    for rm in allocated_rooms:
        rm["subtotal_formatted"] = f"{int(round(rm['subtotal'])):,}".replace(",", " ") + " ₸"

    grouped_blocks = {}
    for rm in allocated_rooms:
        b_title = rm["block"]
        if b_title not in grouped_blocks:
            grouped_blocks[b_title] = []
        grouped_blocks[b_title].append(rm)

    return [{"floor_title": b, "rooms": rms} for b, rms in grouped_blocks.items()]


def build_refills_for_dispensers(
    dispenser_items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Selects certified Essity consumables matching the systems in dispenser_items.
    """
    systems_in_kit = {item.get("system_code", "").upper() for item in dispenser_items}

    catalog_refills = [
        {
            "sku": "290016",
            "name": "Tork Matic® мягкие рулонные полотенца Premium",
            "system_code": "H1",
            "quality": "2 слоя, тиснение «лист», ультрамягкие",
            "description": "100 м в рулоне, полистовая выдача",
            "packaging": "6 рул. / кор.",
            "default_price": 4320
        },
        {
            "sku": "120288",
            "name": "Tork Xpress® мягкие листовые полотенца Multifold",
            "system_code": "H2",
            "quality": "2 слоя, сложение Z, 21 × 25.5 см",
            "description": "190 листов в пачке, ультрапрочные во влажном состоянии",
            "packaging": "20 пач. / кор.",
            "default_price": 14200
        },
        {
            "sku": "472242",
            "name": "Tork SmartOne® туалетная бумага в рулонах Advanced",
            "system_code": "T8",
            "quality": "2 слоя, моментальное растворение за 8 секунд",
            "description": "207 м, 1 150 листов, центральная вытяжка",
            "packaging": "6 рул. / кор.",
            "default_price": 4570
        },
        {
            "sku": "472193",
            "name": "Tork SmartOne® Mini туалетная бумага Advanced",
            "system_code": "T9",
            "quality": "2 слоя, ультрабыстрое растворение 8 сек",
            "description": "111,6 м, 620 листов, компактный рулон",
            "packaging": "12 рул. / кор.",
            "default_price": 4100
        },
        {
            "sku": "520501",
            "name": "Мыло-пена мягкое Tork Premium 1 л",
            "system_code": "S4",
            "quality": "2 500 доз, гипоаллергенное, аромат свежести",
            "description": "Герметичный картридж с встроенным одноразовым насосом",
            "packaging": "6 флак. / кор.",
            "default_price": 5160
        },
        {
            "sku": "525502",
            "name": "Мыло-пена мягкое Tork Premium Mini 525 мл",
            "system_code": "S5",
            "quality": "1 300 доз, pH-нейтральное",
            "description": "Компактный картридж для процедурных и кабинетов",
            "packaging": "8 флак. / кор.",
            "default_price": 3840
        },
        {
            "sku": "204060",
            "name": "Мешки для мусора Tork 50 л сверхпрочные B1",
            "system_code": "B1",
            "quality": "ПВД 30 мкм, скрытая фиксация в корпусе",
            "description": "Рулон 25 шт., защита от протеканий",
            "packaging": "10 рул. / кор. (250 шт.)",
            "default_price": 7500
        }
    ]

    selected_refills = []
    for ref in catalog_refills:
        if ref["system_code"] in systems_in_kit or len(selected_refills) < 3:
            price = ref["default_price"]
            try:
                with get_db_cursor() as cur:
                    cur.execute("SELECT current_price_kzt FROM v_products_active WHERE sku = %s LIMIT 1;", (ref["sku"],))
                    row = cur.fetchone()
                    if row and row.get("current_price_kzt"):
                        price = float(row["current_price_kzt"])
            except Exception:
                pass

            ref_copy = dict(ref)
            ref_copy["price"] = price
            ref_copy["price_formatted"] = f"{int(round(price)):,}".replace(",", " ") + " ₸"
            ref_copy["thumb_data_uri"] = image_to_data_uri(f"images/{ref['sku']}.png")
            selected_refills.append(ref_copy)

    return selected_refills[:4]


def compile_commercial_proposal_kz(
    telegram_id: int,
    company_name: str,
    client_facility: str,
    client_city: Optional[str] = "г. Астана, Казахстан",
    manager_name: Optional[str] = None,
    manager_phone: Optional[str] = None,
    manager_tg: Optional[str] = None,
    items_override: Optional[List[Dict[str, Any]]] = None,
    hero_image_override: Optional[str] = None
) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Deterministic 5-Page Commercial Proposal Generator for Kazakhstan (Phase 4):
    1. Loads manager data from allowed_managers (with user override support).
    2. Loads kit items from session or overrides, pulls prices with 16% VAT.
    3. Calculates 16% VAT, 50% advance / 50% remainder.
    4. Embeds hero visual montage (last_rendered_image_url) on Page 1.
    5. Builds 6-zone room distribution on Page 3.
    6. Injects 4 system infographics on Page 4.
    7. Renders templates/kp_kz_template.html deterministically via Gotenberg.
    8. Generates filename 'КП_Tork_{Компания}_{Дата}.pdf'.
    """
    import re
    from datetime import datetime

    template_str = get_kp_template_html()
    session_data = get_manager_presentation_data(telegram_id)

    # 1. Resolve manager info
    mgr_profile = get_manager_profile_by_tg_id(telegram_id)
    final_manager_name = manager_name or mgr_profile.get("full_name") or session_data.get("client_name") or "Ерлан Кубесов"
    final_manager_phone = manager_phone or mgr_profile.get("phone") or session_data.get("phone") or "+7 (777) 777-77-77"
    raw_tg = manager_tg or mgr_profile.get("username") or session_data.get("tg_username") or "erlan_tork_kz"
    final_manager_tg = f"@{raw_tg.lstrip('@')}"

    final_client_city = client_city or session_data.get("client_city") or "г. Астана, Казахстан"
    final_company_name = company_name or session_data.get("company_name") or "ТОО «Заказчик»"
    final_client_facility = client_facility or session_data.get("client_facility") or "Гостиничный комплекс, 5 этажей, 42 санузла"

    # 2. Resolve dispenser items
    raw_items = items_override
    if not raw_items:
        bundle = session_data.get("selected_bundle")
        if bundle:
            if isinstance(bundle, list) and len(bundle) > 0:
                raw_items = bundle
            elif isinstance(bundle, dict) and "items" in bundle:
                raw_items = bundle["items"]

    if not raw_items:
        raw_items = [
            {"sku": "551000", "count": 16, "name": "Tork Matic® диспенсер для полотенец в рулоне", "system_code": "H1", "color": "Белый Elevation", "dimensions": "37,2 × 33,7 × 20,3 см", "price": 89000},
            {"sku": "680008", "count": 20, "name": "Tork SmartOne® диспенсер для туалетной бумаги", "system_code": "T8", "color": "Черный Elevation", "dimensions": "26,9 × 26,9 × 15,6 см", "price": 43500},
            {"sku": "564500", "count": 12, "name": "Tork диспенсер для мыла-пены S4", "system_code": "S4", "color": "Белый Elevation", "dimensions": "29 × 11,2 × 9,9 см", "price": 36500},
            {"sku": "563000", "count": 8,  "name": "Tork корзина для мусора 50 л со скрытым мешком B1", "system_code": "B1", "color": "Белый Elevation", "dimensions": "62,9 × 38,9 × 18,9 см", "price": 65000}
        ]

    dispenser_items = []
    for it in raw_items:
        sku = str(it.get("sku", "551000")).strip()
        cnt = int(it.get("count", 1) or 1)
        name = it.get("name")
        system_code = (it.get("system_code") or "H1").upper()
        color = it.get("color") or "Белый Elevation"
        dimensions = it.get("dimensions") or "37,2 × 33,7 × 20,3 см"
        price = it.get("price")

        try:
            with get_db_cursor() as cur:
                cur.execute(
                    """
                    SELECT name, system_code, color, dimensions_cm, current_price_kzt
                    FROM v_products_active
                    WHERE sku = %s LIMIT 1;
                    """,
                    (sku,)
                )
                p_row = cur.fetchone()
                if p_row:
                    name = name or p_row.get("name")
                    system_code = system_code or p_row.get("system_code") or "H1"
                    if p_row.get("color"):
                        color = p_row["color"]
                    if not price and p_row.get("current_price_kzt"):
                        price = float(p_row["current_price_kzt"])
                    if p_row.get("dimensions_cm") and isinstance(p_row["dimensions_cm"], dict):
                        d = p_row["dimensions_cm"]
                        dimensions = f"{d.get('height', 30)} × {d.get('width', 30)} × {d.get('depth', 15)} см"
        except Exception as e:
            logger.warning(f"Error resolving product SKU {sku} from DB: {e}")

        price = float(price or 45000)
        total_item = price * cnt

        thumb_uri = image_to_data_uri(f"images/{sku}.png")

        dispenser_items.append({
            "sku": sku,
            "name": name or f"Tork диспенсер {system_code}",
            "system_code": system_code,
            "color": color,
            "dimensions": dimensions,
            "count": cnt,
            "price": price,
            "price_formatted": f"{int(round(price)):,}".replace(",", " ") + " ₸",
            "total": total_item,
            "total_formatted": f"{int(round(total_item)):,}".replace(",", " ") + " ₸",
            "thumb_data_uri": thumb_uri
        })

    # 3. Financial & Tax Calculations (Kazakhstan 16% VAT)
    total_dispensers_count = sum(d["count"] for d in dispenser_items)
    total_amount = sum(d["total"] for d in dispenser_items)
    # 16% VAT portion within total
    vat_amount = round(total_amount * 16 / 116)
    prepayment_amount = round(total_amount * 0.5)
    postpayment_amount = total_amount - prepayment_amount

    # 4. Hero Visual Montage (Page 1)
    hero_source = hero_image_override or session_data.get("last_rendered_image_url")
    if not hero_source or len(str(hero_source).strip()) < 150:
        hero_source = "sample_fittings/gemini_multi_kit_fitting.jpg"

    hero_image_data_uri = image_to_data_uri(hero_source, default_rel_path="sample_fittings/gemini_multi_kit_fitting.jpg")

    # 5. Matching Refills (Page 2)
    refill_items = build_refills_for_dispensers(dispenser_items)

    # 6. Room Distribution Plan (Page 3)
    distribution_groups = build_room_distribution(dispenser_items, final_client_facility)

    # 7. Dates and formatting
    now = datetime.now()
    kp_date = f"{now.day:02d} {MONTHS_RU.get(now.month, 'ноября')} {now.year} г."
    date_str = now.strftime("%d_%m_%Y")

    clean_company = re.sub(r'[^\w\-_]', '_', final_company_name.strip()).strip('_')
    if not clean_company:
        clean_company = "Client"
    filename = f"КП_Tork_{clean_company}_{date_str}.pdf"

    context = {
        "client_name": final_company_name,
        "client_facility": final_client_facility,
        "client_city": final_client_city,
        "kp_date": kp_date,
        "manager_name": final_manager_name,
        "manager_phone": final_manager_phone,
        "manager_tg": final_manager_tg,
        "total_amount_formatted": f"{int(round(total_amount)):,}".replace(",", " "),
        "vat_amount_formatted": f"{int(round(vat_amount)):,}".replace(",", " "),
        "prepayment_amount_formatted": f"{int(round(prepayment_amount)):,}".replace(",", " "),
        "postpayment_amount_formatted": f"{int(round(postpayment_amount)):,}".replace(",", " "),
        "total_dispensers_count": str(total_dispensers_count),
        "dispenser_items": dispenser_items,
        "refill_items": refill_items,
        "distribution_groups": distribution_groups,
        "hero_image_data_uri": hero_image_data_uri
    }

    jinja_env = jinja2.Environment(autoescape=True)
    tpl = jinja_env.from_string(template_str)
    rendered_html = tpl.render(**context)

    pdf_bytes = call_gotenberg_html_to_pdf(rendered_html)

    try:
        out_dir = None
        for d in OUTPUT_SEARCH_DIRS:
            if d:
                os.makedirs(d, exist_ok=True)
                out_dir = d
                break
        if out_dir:
            file_path = os.path.join(out_dir, filename)
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"Saved generated commercial proposal to {file_path}")
    except Exception as e:
        logger.warning(f"Failed to persist KP copy to disk: {e}")

    metadata = {
        "filename": filename,
        "client_name": final_company_name,
        "client_facility": final_client_facility,
        "client_city": final_client_city,
        "manager_name": final_manager_name,
        "manager_phone": final_manager_phone,
        "total_amount": total_amount,
        "vat_amount": vat_amount,
        "prepayment_amount": prepayment_amount,
        "postpayment_amount": postpayment_amount,
        "total_dispensers_count": total_dispensers_count,
        "size_bytes": len(pdf_bytes)
    }

    return pdf_bytes, filename, metadata

