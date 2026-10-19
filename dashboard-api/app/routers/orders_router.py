import os
import math
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from app.auth import get_current_user
from app.database import get_db_cursor
from app.models import Role, ALLOWED_ORDER_STATUSES
from app.schemas import (
    UserProfile,
    OrdersListResponse,
    OrderListItem,
    OrderDetailResponse,
    OrderStatusUpdateRequest,
)

router = APIRouter(prefix="/api/admin/orders", tags=["Orders Management"])

def parse_bundle(bundle_raw: Any) -> Any:
    if bundle_raw is None:
        return []
    if isinstance(bundle_raw, (list, dict)):
        return bundle_raw
    if isinstance(bundle_raw, str):
        try:
            return json.loads(bundle_raw)
        except Exception:
            return []
    return []

def compute_order_total(selected_bundle: Any) -> float:
    bundle = parse_bundle(selected_bundle)
    if isinstance(bundle, dict):
        if "total_amount" in bundle:
            try:
                return float(bundle["total_amount"])
            except (ValueError, TypeError):
                pass
        items = bundle.get("items", [])
    elif isinstance(bundle, list):
        items = bundle
    else:
        items = []

    total = 0.0
    for item in items:
        if isinstance(item, dict):
            if item.get("line_total") is not None:
                try:
                    total += float(item["line_total"])
                    continue
                except (ValueError, TypeError):
                    pass
            price = item.get("price", 0)
            qty = item.get("qty", 1)
            try:
                total += float(price) * float(qty)
            except (ValueError, TypeError):
                pass
    return round(total, 2)

def extract_meta(selected_bundle: Any, row: dict) -> tuple[str, str]:
    bin_val = row.get("distributor_bin") or ""
    city_val = row.get("distributor_city") or ""

    bundle = parse_bundle(selected_bundle)
    if isinstance(bundle, dict):
        if bundle.get("bin"):
            bin_val = str(bundle["bin"])
        if bundle.get("city"):
            city_val = str(bundle["city"])

    return bin_val, city_val


@router.get("", response_model=OrdersListResponse)
def get_orders(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by order status"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    distributor_id: Optional[int] = Query(None, description="Filter by distributor ID (vendor only)"),
    search: Optional[str] = Query(None, description="Search by kp_number, company_name, bin, client_name, phone"),
    current_user: UserProfile = Depends(get_current_user),
):
    where_clauses = ["(o.current_step = 'ORDER_COMPLETED' OR o.selected_bundle IS NOT NULL)"]
    params = []

    # RBAC Data Isolation
    if current_user.role == Role.DISTRIBUTOR_MANAGER.value:
        # Strictly enforce manager's assigned distributor
        if current_user.distributor_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Distributor manager is not assigned to any distributor",
            )
        where_clauses.append("o.distributor_id = %s")
        params.append(current_user.distributor_id)
    else:
        # Vendor admin can optionally filter by distributor_id
        if distributor_id is not None:
            where_clauses.append("o.distributor_id = %s")
            params.append(distributor_id)

    # Optional filter by order_status
    if status:
        where_clauses.append("o.order_status = %s")
        params.append(status)

    # Optional filter by city
    if city:
        where_clauses.append("(LOWER(d.city) = LOWER(%s) OR LOWER(COALESCE(o.selected_bundle->>'city', '')) = LOWER(%s))")
        params.extend([city, city])

    # Optional search query across kp_number, company_name, client_name, phone, BIN
    if search and search.strip():
        s_term = f"%{search.strip()}%"
        where_clauses.append(
            "(o.kp_number ILIKE %s OR o.company_name ILIKE %s OR o.client_name ILIKE %s OR o.phone ILIKE %s OR d.bin ILIKE %s OR COALESCE(o.selected_bundle->>'bin', '') ILIKE %s)"
        )
        params.extend([s_term, s_term, s_term, s_term, s_term, s_term])

    where_sql = " AND ".join(where_clauses)

    with get_db_cursor() as cur:
        # 1. Count total
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE {where_sql};
        """
        cur.execute(count_query, params)
        total = cur.fetchone()["total"]

        # 2. Fetch page items
        offset = (page - 1) * limit
        fetch_query = f"""
            SELECT 
                o.id,
                o.kp_number,
                o.company_name,
                o.phone,
                o.client_name,
                COALESCE(o.order_status, 'NEW') AS order_status,
                o.distributor_id,
                d.name AS distributor_name,
                d.city AS distributor_city,
                d.bin AS distributor_bin,
                o.selected_bundle,
                o.created_at,
                o.updated_at
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE {where_sql}
            ORDER BY o.updated_at DESC, o.id DESC
            LIMIT %s OFFSET %s;
        """
        cur.execute(fetch_query, params + [limit, offset])
        rows = cur.fetchall()

    pages = math.ceil(total / limit) if total > 0 else 1

    items = []
    now = datetime.now(timezone.utc)
    for r in rows:
        bin_val, city_val = extract_meta(r["selected_bundle"], r)
        total_amount = compute_order_total(r["selected_bundle"])

        sla_breached = False
        wait_time_hours = None
        if r["order_status"] == "NEW" and r["created_at"]:
            created_dt = r["created_at"]
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            diff_hours = (now - created_dt).total_seconds() / 3600.0
            wait_time_hours = round(diff_hours, 1)
            if diff_hours > 2.0:
                sla_breached = True

        items.append(
            OrderListItem(
                id=r["id"],
                kp_number=r["kp_number"],
                company_name=r["company_name"],
                bin=bin_val,
                city=city_val,
                phone=r["phone"],
                client_name=r["client_name"],
                order_status=r["order_status"],
                total_amount=total_amount,
                distributor_id=r["distributor_id"],
                distributor_name=r["distributor_name"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                sla_breached=sla_breached,
                wait_time_hours=wait_time_hours,
            )
        )

    return OrdersListResponse(
        items=items,
        total=total,
        pages=pages,
        page=page,
        limit=limit,
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order_detail(
    order_id: int,
    current_user: UserProfile = Depends(get_current_user),
):
    with get_db_cursor() as cur:
        query = """
            SELECT 
                o.id,
                o.kp_number,
                o.company_name,
                o.phone,
                o.client_name,
                o.tg_user_id,
                o.tg_username,
                COALESCE(o.order_status, 'NEW') AS order_status,
                COALESCE(o.manager_notes, '') AS manager_notes,
                o.distributor_id,
                d.name AS distributor_name,
                d.city AS distributor_city,
                d.bin AS distributor_bin,
                o.selected_bundle,
                o.created_at,
                o.updated_at
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE o.id = %s;
        """
        cur.execute(query, (order_id,))
        order = cur.fetchone()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order #{order_id} not found",
        )

    # RBAC: Distributor manager can only view orders of their own distributor
    if current_user.role == Role.DISTRIBUTOR_MANAGER.value:
        if order["distributor_id"] != current_user.distributor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to access orders from another region",
            )

    bin_val, city_val = extract_meta(order["selected_bundle"], order)
    total_amount = compute_order_total(order["selected_bundle"])
    bundle_parsed = parse_bundle(order["selected_bundle"])

    sla_breached = False
    wait_time_hours = None
    if order["order_status"] == "NEW" and order["created_at"]:
        created_dt = order["created_at"]
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        diff_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600.0
        wait_time_hours = round(diff_hours, 1)
        if diff_hours > 2.0:
            sla_breached = True

    return OrderDetailResponse(
        id=order["id"],
        kp_number=order["kp_number"],
        company_name=order["company_name"],
        bin=bin_val,
        city=city_val,
        phone=order["phone"],
        client_name=order["client_name"],
        tg_user_id=order["tg_user_id"],
        tg_username=order["tg_username"],
        order_status=order["order_status"],
        manager_notes=order["manager_notes"],
        total_amount=total_amount,
        distributor_id=order["distributor_id"],
        distributor_name=order["distributor_name"],
        selected_bundle=bundle_parsed,
        created_at=order["created_at"],
        updated_at=order["updated_at"],
        sla_breached=sla_breached,
        wait_time_hours=wait_time_hours,
    )


@router.patch("/{order_id}/status", response_model=OrderDetailResponse)
def update_order_status(
    order_id: int,
    body: OrderStatusUpdateRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    if body.order_status not in ALLOWED_ORDER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order_status '{body.order_status}'. Allowed values: {sorted(list(ALLOWED_ORDER_STATUSES))}",
        )

    with get_db_cursor() as cur:
        # Check existing order
        cur.execute("SELECT id, distributor_id FROM user_sessions_leads WHERE id = %s;", (order_id,))
        existing = cur.fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order #{order_id} not found",
            )

        # RBAC Check: Distributor can only update their own region
        if current_user.role == Role.DISTRIBUTOR_MANAGER.value:
            if existing["distributor_id"] != current_user.distributor_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You can only update orders from your assigned region",
                )

        # Update order
        if body.manager_notes is not None:
            update_sql = """
                UPDATE user_sessions_leads
                SET order_status = %s,
                    manager_notes = %s,
                    updated_at = NOW()
                WHERE id = %s;
            """
            cur.execute(update_sql, (body.order_status, body.manager_notes, order_id))
        else:
            update_sql = """
                UPDATE user_sessions_leads
                SET order_status = %s,
                    updated_at = NOW()
                WHERE id = %s;
            """
            cur.execute(update_sql, (body.order_status, order_id))

        # Re-fetch full updated order
        detail_query = """
            SELECT 
                o.id,
                o.kp_number,
                o.company_name,
                o.phone,
                o.client_name,
                o.tg_user_id,
                o.tg_username,
                COALESCE(o.order_status, 'NEW') AS order_status,
                COALESCE(o.manager_notes, '') AS manager_notes,
                o.distributor_id,
                d.name AS distributor_name,
                d.city AS distributor_city,
                d.bin AS distributor_bin,
                o.selected_bundle,
                o.created_at,
                o.updated_at
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE o.id = %s;
        """
        cur.execute(detail_query, (order_id,))
        updated = cur.fetchone()

    bin_val, city_val = extract_meta(updated["selected_bundle"], updated)
    total_amount = compute_order_total(updated["selected_bundle"])
    bundle_parsed = parse_bundle(updated["selected_bundle"])

    return OrderDetailResponse(
        id=updated["id"],
        kp_number=updated["kp_number"],
        company_name=updated["company_name"],
        bin=bin_val,
        city=city_val,
        phone=updated["phone"],
        client_name=updated["client_name"],
        tg_user_id=updated["tg_user_id"],
        tg_username=updated["tg_username"],
        order_status=updated["order_status"],
        manager_notes=updated["manager_notes"],
        total_amount=total_amount,
        distributor_id=updated["distributor_id"],
        distributor_name=updated["distributor_name"],
        selected_bundle=bundle_parsed,
        created_at=updated["created_at"],
        updated_at=updated["updated_at"],
    )


@router.get("/{order_id}/pdf")
def get_order_pdf(
    order_id: int,
    current_user: UserProfile = Depends(get_current_user),
):
    with get_db_cursor() as cur:
        query = """
            SELECT 
                o.id,
                o.kp_number,
                o.company_name,
                o.phone,
                o.client_name,
                o.tg_user_id,
                o.tg_username,
                COALESCE(o.order_status, 'NEW') AS order_status,
                COALESCE(o.manager_notes, '') AS manager_notes,
                o.distributor_id,
                d.name AS distributor_name,
                d.bin AS distributor_bin,
                d.city AS distributor_city,
                d.address AS distributor_address,
                d.contact_phone AS distributor_phone,
                d.contact_email AS distributor_email,
                o.selected_bundle,
                o.created_at,
                o.updated_at
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE o.id = %s;
        """
        cur.execute(query, (order_id,))
        order = cur.fetchone()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order #{order_id} not found",
        )

    # RBAC: Distributor manager can only download orders of their own distributor
    if current_user.role == Role.DISTRIBUTOR_MANAGER.value:
        if order["distributor_id"] != current_user.distributor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have permission to download orders from another region",
            )

    bundle = parse_bundle(order["selected_bundle"])
    if isinstance(bundle, dict):
        items = bundle.get("items", [])
    elif isinstance(bundle, list):
        items = bundle
    else:
        items = []

    table_rows_html = ""
    for idx, itm in enumerate(items, 1):
        if not isinstance(itm, dict):
            continue
        sku = str(itm.get("sku", "")).strip()
        name = str(itm.get("name", "Товар Tork"))
        system = str(itm.get("system_code") or "—")
        try:
            qty = int(itm.get("qty", 1))
        except (ValueError, TypeError):
            qty = 1
        try:
            price = float(itm.get("price", 0))
        except (ValueError, TypeError):
            price = 0.0
        try:
            line_total = float(itm.get("line_total", price * qty))
        except (ValueError, TypeError):
            line_total = price * qty

        price_str = f"{int(round(price)):,}".replace(",", " ")
        line_total_str = f"{int(round(line_total)):,}".replace(",", " ")

        img_tag = f'<img src="http://cdn/images/{sku}.png" width="34" height="34" style="object-fit:contain; vertical-align:middle; margin-right:8px; border-radius:3px; border:1px solid #E2E8F0; background:#fff;" onerror="this.style.display=\'none\'" />'

        table_rows_html += f"""
        <tr>
          <td class="text-center">{idx}</td>
          <td><strong>{sku}</strong></td>
          <td><div style="display:flex; align-items:center;">{img_tag}<span>{name}</span></div></td>
          <td class="text-center"><span class="badge">{system}</span></td>
          <td class="text-center">{qty}</td>
          <td class="text-right">{price_str} ₸</td>
          <td class="text-right"><strong>{line_total_str} ₸</strong></td>
        </tr>
        """

    if not table_rows_html:
        table_rows_html = '<tr><td colspan="7" class="text-center" style="padding:16px;">Спецификация заказа не содержит товаров</td></tr>'

    total_amount = compute_order_total(order["selected_bundle"])
    total_amount_formatted = f"{int(round(total_amount)):,}".replace(",", " ")

    kp_num = order["kp_number"] or f"TKZ-{order['id']:06d}"
    created_dt = order["created_at"]
    kp_date_str = created_dt.strftime("%d.%m.%Y") if created_dt else "19.10.2026"

    bin_val, city_val = extract_meta(order["selected_bundle"], order)
    if order["company_name"] and order["client_name"]:
        client_formatted = f"{order['company_name']} (контакт: {order['client_name']})"
    else:
        client_formatted = order["company_name"] or order["client_name"] or "Уважаемый клиент"

    replacements = {
        "distributor_name": order["distributor_name"] or 'ТОО "Tork Kazakhstan Distribution"',
        "distributor_bin": order["distributor_bin"] or "210540032111",
        "distributor_city": order["distributor_city"] or "г. Астана",
        "distributor_address": order["distributor_address"] or 'г. Астана, район Есиль, ул. Достык, 18, БЦ "Москва", офис 704',
        "distributor_phone": order["distributor_phone"] or "+7 (7172) 79-55-01",
        "distributor_email": order["distributor_email"] or "astana@tork-distrib.kz",
        "kp_number": kp_num,
        "kp_date": kp_date_str,
        "client_name": client_formatted,
        "bin": bin_val or "—",
        "city": city_val or "Казахстан",
        "phone": order["phone"] or "—",
        "table_rows_html": table_rows_html,
        "total_amount_formatted": total_amount_formatted,
    }

    # Locate template file
    template_paths = [
        Path("/app/templates/kp_catalog_template.html"),
        Path("/data/templates/kp_catalog_template.html"),
        Path(__file__).resolve().parent.parent.parent / "templates" / "kp_catalog_template.html",
        Path("templates/kp_catalog_template.html"),
    ]

    html_template = None
    for p in template_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    html_template = f.read()
                break
            except Exception:
                continue

    if not html_template:
        html_template = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Коммерческое предложение {{ kp_number }}</title></head>
<body style="font-family:sans-serif; padding:20px;">
  <h2>Коммерческое предложение Tork — № {{ kp_number }} ({{ kp_date }})</h2>
  <p><strong>Поставщик:</strong> {{ distributor_name }} (БИН: {{ distributor_bin }})</p>
  <p><strong>Клиент:</strong> {{ client_name }} (БИН: {{ bin }}, Телефон: {{ phone }})</p>
  <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%; margin-top:15px;">
    <thead><tr><th>№</th><th>Артикул</th><th>Наименование</th><th>Система</th><th>Кол-во</th><th>Цена (₸)</th><th>Сумма (₸)</th></tr></thead>
    <tbody>{{ table_rows_html }}</tbody>
  </table>
  <h3 style="margin-top:20px;">Итого к оплате (с НДС 12%): {{ total_amount_formatted }} ₸</h3>
</body></html>"""

    rendered_html = html_template
    for key, val in replacements.items():
        rendered_html = rendered_html.replace("{{ " + key + " }}", str(val)).replace("{{" + key + "}}", str(val))

    gotenberg_url = os.getenv("GOTENBERG_URL", "http://gotenberg:3000")
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="index.html"\r\n'
        f"Content-Type: text/html; charset=utf-8\r\n\r\n"
        f"{rendered_html}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{gotenberg_url}/forms/chromium/convert/html",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pdf_bytes = resp.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to render PDF via Gotenberg: {str(exc)}",
        )

    safe_filename = f"KP_Tork_{kp_num}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

