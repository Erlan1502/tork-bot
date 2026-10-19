import math
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import get_current_user
from app.database import get_db_cursor
from app.models import Role
from app.schemas import (
    UserProfile,
    AnalyticsSummaryResponse,
    RegionShare,
    ChannelBreakdown,
    TopProductItem,
    AnalyticsSlaResponse,
    BreachedLeadItem,
)
from app.routers.orders_router import compute_order_total, parse_bundle

router = APIRouter(prefix="/api/admin/analytics", tags=["Vendor Analytics"])

def require_vendor_admin(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    if current_user.role != Role.VENDOR_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only vendor_admin can access analytics",
        )
    return current_user


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(
    current_user: UserProfile = Depends(require_vendor_admin),
):
    with get_db_cursor() as cur:
        # Fetch distributors
        cur.execute("SELECT id, name, city FROM distributors ORDER BY id;")
        distributors = cur.fetchall()

        # Fetch all completed or active orders
        cur.execute("""
            SELECT 
                o.id,
                o.distributor_id,
                o.selected_bundle,
                o.current_step,
                o.order_status,
                o.created_at,
                o.updated_at,
                o.last_photo_file_id,
                o.renders_today,
                COALESCE(o.lead_source, 'direct_catalog') AS lead_source,
                d.city AS distributor_city
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE (o.current_step = 'ORDER_COMPLETED' OR o.selected_bundle IS NOT NULL);
        """)
        orders = cur.fetchall()

    total_revenue_kzt = 0.0
    total_orders_count = len(orders)

    # Initialize region stats map
    region_map: Dict[int, Dict[str, Any]] = {}
    for d in distributors:
        region_map[d["id"]] = {
            "distributor_id": d["id"],
            "city": d["city"],
            "orders_count": 0,
            "revenue_kzt": 0.0,
        }

    direct_catalog_count = 0
    ai_fitting_count = 0

    for o in orders:
        bundle_total = compute_order_total(o["selected_bundle"])
        total_revenue_kzt += bundle_total

        # Assign to region
        dist_id = o.get("distributor_id")
        if dist_id in region_map:
            region_map[dist_id]["orders_count"] += 1
            region_map[dist_id]["revenue_kzt"] += bundle_total
        elif region_map:
            # Fallback to first distributor if unassigned
            first_id = list(region_map.keys())[0]
            region_map[first_id]["orders_count"] += 1
            region_map[first_id]["revenue_kzt"] += bundle_total

        # Channel attribution
        bundle_data = parse_bundle(o["selected_bundle"])
        is_bundle_ai = isinstance(bundle_data, dict) and bundle_data.get("source") == "ai_fitting"
        is_fitting = (
            bool(o.get("last_photo_file_id"))
            or (o.get("renders_today") is not None and o["renders_today"] > 0)
            or (o.get("lead_source") == "ai_fitting")
            or is_bundle_ai
        )

        if is_fitting:
            ai_fitting_count += 1
        else:
            direct_catalog_count += 1

    total_revenue_kzt = round(total_revenue_kzt, 2)
    average_check_kzt = round(total_revenue_kzt / total_orders_count) if total_orders_count > 0 else 0.0

    by_region: List[RegionShare] = []
    for dist_id, r in sorted(region_map.items()):
        rev = round(r["revenue_kzt"], 2)
        share = round((rev / total_revenue_kzt) * 100.0, 1) if total_revenue_kzt > 0 else 0.0
        by_region.append(
            RegionShare(
                distributor_id=r["distributor_id"],
                city=r["city"],
                orders_count=r["orders_count"],
                revenue_kzt=rev,
                share_percent=share,
            )
        )

    return AnalyticsSummaryResponse(
        total_revenue_kzt=total_revenue_kzt,
        total_orders_count=total_orders_count,
        average_check_kzt=average_check_kzt,
        by_region=by_region,
        by_channel=ChannelBreakdown(
            direct_catalog_count=direct_catalog_count,
            ai_fitting_count=ai_fitting_count,
        ),
    )


@router.get("/top-products", response_model=List[TopProductItem])
def get_top_products(
    current_user: UserProfile = Depends(require_vendor_admin),
):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT selected_bundle 
            FROM user_sessions_leads 
            WHERE (current_step = 'ORDER_COMPLETED' OR selected_bundle IS NOT NULL);
        """)
        orders = cur.fetchall()

    product_agg: Dict[str, Dict[str, Any]] = {}

    for o in orders:
        bundle = parse_bundle(o["selected_bundle"])
        if isinstance(bundle, dict):
            items = bundle.get("items", [])
        elif isinstance(bundle, list):
            items = bundle
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            sku = str(item.get("sku") or "").strip()
            if not sku:
                continue

            try:
                qty = int(item.get("qty") or 1)
            except (ValueError, TypeError):
                qty = 1

            price = 0.0
            try:
                price = float(item.get("price") or 0.0)
            except (ValueError, TypeError):
                pass

            line_total = 0.0
            if item.get("line_total") is not None:
                try:
                    line_total = float(item["line_total"])
                except (ValueError, TypeError):
                    line_total = price * qty
            else:
                line_total = price * qty

            name = item.get("name") or ""
            system_code = item.get("system_code") or ""

            if sku not in product_agg:
                product_agg[sku] = {
                    "sku": sku,
                    "name": name,
                    "system_code": system_code,
                    "total_qty": 0,
                    "total_revenue_kzt": 0.0,
                }

            product_agg[sku]["total_qty"] += qty
            product_agg[sku]["total_revenue_kzt"] += line_total
            if not product_agg[sku]["name"] and name:
                product_agg[sku]["name"] = name
            if not product_agg[sku]["system_code"] and system_code:
                product_agg[sku]["system_code"] = system_code

    # Fill missing product names or system_codes from DB products table
    missing_skus = [sku for sku, v in product_agg.items() if not v["name"] or not v["system_code"]]
    if missing_skus:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT sku, name, system_code 
                FROM products 
                WHERE sku = ANY(%s);
            """, (missing_skus,))
            for r in cur.fetchall():
                sku_db = str(r["sku"]).strip()
                if sku_db in product_agg:
                    if not product_agg[sku_db]["name"]:
                        product_agg[sku_db]["name"] = r["name"] or ""
                    if not product_agg[sku_db]["system_code"]:
                        product_agg[sku_db]["system_code"] = r["system_code"] or ""

    # Sort descending by total_revenue_kzt, then total_qty
    sorted_items = sorted(
        product_agg.values(),
        key=lambda x: (x["total_revenue_kzt"], x["total_qty"]),
        reverse=True,
    )[:10]

    result = [
        TopProductItem(
            sku=p["sku"],
            name=p["name"] or f"Tork {p['sku']}",
            system_code=p["system_code"] or "—",
            total_qty=p["total_qty"],
            total_revenue_kzt=round(p["total_revenue_kzt"], 2),
        )
        for p in sorted_items
    ]
    return result


@router.get("/sla", response_model=AnalyticsSlaResponse)
def get_sla_analytics(
    current_user: UserProfile = Depends(require_vendor_admin),
):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT 
                o.id,
                o.kp_number,
                o.company_name,
                o.client_name,
                o.phone,
                COALESCE(o.order_status, 'NEW') AS order_status,
                o.distributor_id,
                d.city AS distributor_city,
                o.created_at,
                o.updated_at
            FROM user_sessions_leads o
            LEFT JOIN distributors d ON o.distributor_id = d.id
            WHERE (o.current_step = 'ORDER_COMPLETED' OR o.selected_bundle IS NOT NULL)
            ORDER BY o.created_at ASC;
        """)
        orders = cur.fetchall()

    now = datetime.now(timezone.utc)
    transition_times_min = []
    breached_leads: List[BreachedLeadItem] = []

    for o in orders:
        status_val = o["order_status"]
        created = o["created_at"]
        updated = o["updated_at"]

        # Reaction time calculation for orders transitioned from NEW
        if status_val != "NEW" and created and updated:
            created_dt = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            updated_dt = updated if updated.tzinfo else updated.replace(tzinfo=timezone.utc)
            delta_min = (updated_dt - created_dt).total_seconds() / 60.0
            if delta_min > 0:
                transition_times_min.append(delta_min)

        # SLA breach check for pending NEW orders (> 2 hours)
        if status_val == "NEW" and created:
            created_dt = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            diff_hours = (now - created_dt).total_seconds() / 3600.0
            if diff_hours > 2.0:
                h = int(diff_hours)
                m = int((diff_hours - h) * 60)
                formatted_wait = f"{h} ч {m} мин" if h > 0 else f"{m} мин"
                breached_leads.append(
                    BreachedLeadItem(
                        id=o["id"],
                        kp_number=o["kp_number"],
                        company_name=o["company_name"],
                        city=o["distributor_city"],
                        client_name=o["client_name"],
                        phone=o["phone"],
                        order_status=status_val,
                        created_at=o["created_at"],
                        wait_time_hours=round(diff_hours, 1),
                        wait_time_formatted=formatted_wait,
                        sla_breached=True,
                    )
                )

    avg_minutes = (sum(transition_times_min) / len(transition_times_min)) if transition_times_min else 0.0
    if avg_minutes >= 60:
        h = int(avg_minutes // 60)
        m = int(avg_minutes % 60)
        formatted_avg = f"{h} ч {m} мин"
    elif avg_minutes > 0:
        formatted_avg = f"{int(avg_minutes)} мин"
    else:
        formatted_avg = "0 мин"

    return AnalyticsSlaResponse(
        average_response_time_minutes=round(avg_minutes, 1),
        average_response_time_formatted=formatted_avg,
        processed_orders_count=len(transition_times_min),
        breached_leads_count=len(breached_leads),
        breached_leads=breached_leads,
    )
