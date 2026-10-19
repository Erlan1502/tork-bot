import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from app.database import get_db_cursor

logger = logging.getLogger(__name__)

def calculate_zone(product_type: str, system_code: str, name: str) -> str:
    pt = (product_type or "").strip().lower()
    sc = (system_code or "").strip().upper()
    nm = (name or "").strip()

    # Rule 3: zone_accessories («Оснащение и гигиена»)
    if pt in ("bin", "accessory", "air_freshener") or (pt == "napkin" and sc == "F1"):
        return "zone_accessories"

    # Rule 2: zone_toilet («Туалетная зона»)
    if pt in ("toilet_paper", "seat_cover"):
        return "zone_toilet"

    # Rule 4: zone_wiping («Протирочные материалы»)
    wiping_systems = {"N4", "N14", "M1", "M2", "M4", "W1", "W2", "W3", "W4", "W10", "W14"}
    if pt == "wiper" or sc in wiping_systems or sc.startswith("W") or "linstyle" in nm.lower():
        return "zone_wiping"

    # Rule 1: zone_wash («Зона мытья рук»)
    if pt in ("hand_towel", "soap"):
        return "zone_wash"

    return "zone_wash"

def export_catalog_to_file() -> int:
    """
    Exports all products where is_active_in_catalog is True to ./webapp/products.json
    Returns the number of exported active products.
    """
    query = """
    SELECT 
        sku,
        name,
        category,
        product_type,
        system_code,
        color,
        current_price_kzt,
        COALESCE(description, '') as description
    FROM v_products_active
    WHERE COALESCE(is_active_in_catalog, true) = true
    ORDER BY sku ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    catalog = []
    for row in rows:
        sku = str(row["sku"]).strip()
        name = (row["name"] or "").strip()
        category = (row["category"] or "dispenser").strip()
        product_type = (row["product_type"] or "").strip()
        system_code = (row["system_code"] or "").strip()
        color = (row["color"] or "none").strip()
        price_val = float(row["current_price_kzt"]) if row["current_price_kzt"] is not None else 0.0
        description = (row["description"] or "").strip()
        zone = calculate_zone(product_type, system_code, name)

        item = {
            "sku": sku,
            "name": name,
            "category": category,
            "product_type": product_type,
            "system_code": system_code,
            "color": color,
            "price": price_val,
            "image_url": f"/images/{sku}.png",
            "description": description,
            "zone": zone,
        }
        catalog.append(item)

    target_paths = [
        Path("/app/webapp/products.json"),
        Path(__file__).resolve().parents[3] / "webapp" / "products.json",
        Path(__file__).resolve().parents[2] / "webapp" / "products.json",
        Path.cwd() / "webapp" / "products.json",
    ]

    written_paths = []
    seen = set()
    for p in target_paths:
        try:
            norm_str = str(p.resolve())
            if norm_str in seen:
                continue
            seen.add(norm_str)
            if p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(catalog, f, ensure_ascii=False, indent=2)
                written_paths.append(str(p))
        except Exception as e:
            logger.warning(f"Could not write catalog to {p}: {e}")

    logger.info(f"Catalog exported with {len(catalog)} active items to: {written_paths}")
    return len(catalog)
