"""
Export catalog from PostgreSQL (v_products_active) to ./webapp/products.json
Categorization follows Variant A:
  1. zone_wash («Зона мытья рук»): product_type IN ('hand_towel', 'soap')
  2. zone_toilet («Туалетная зона»): product_type IN ('toilet_paper', 'seat_cover')
  3. zone_accessories («Оснащение и гигиена»): product_type IN ('bin', 'accessory', 'air_freshener') OR (product_type = 'napkin' AND system_code = 'F1')
  4. zone_wiping («Протирочные материалы»): product_type = 'wiper' OR system_code IN ('N4', 'N14', 'M1', 'M2', 'M4', 'W1', 'W2', 'W3', 'W4', 'W10', 'W14') OR LinStyle
"""

import os
import json
import psycopg2
from pathlib import Path

def load_env(env_path: Path):
    if not env_path.exists():
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v

def calculate_zone(product_type: str, system_code: str, name: str) -> str:
    pt = (product_type or '').strip().lower()
    sc = (system_code or '').strip().upper()
    nm = (name or '').strip()

    # Rule 3: zone_accessories («Оснащение и гигиена»)
    if pt in ('bin', 'accessory', 'air_freshener') or (pt == 'napkin' and sc == 'F1'):
        return 'zone_accessories'

    # Rule 2: zone_toilet («Туалетная зона»)
    if pt in ('toilet_paper', 'seat_cover'):
        return 'zone_toilet'

    # Rule 4: zone_wiping («Протирочные материалы»)
    wiping_systems = {'N4', 'N14', 'M1', 'M2', 'M4', 'W1', 'W2', 'W3', 'W4', 'W10', 'W14'}
    if pt == 'wiper' or sc in wiping_systems or sc.startswith('W') or 'linstyle' in nm.lower():
        return 'zone_wiping'

    # Rule 1: zone_wash («Зона мытья рук»)
    if pt in ('hand_towel', 'soap'):
        return 'zone_wash'

    return 'zone_wash'

def main():
    root_dir = Path(__file__).resolve().parent.parent
    load_env(root_dir / '.env')

    db_host = os.environ.get('POSTGRES_HOST', 'localhost')
    db_port = int(os.environ.get('POSTGRES_PORT', '5432'))
    db_name = os.environ.get('POSTGRES_DB', 'tork_bot_db')
    db_user = os.environ.get('POSTGRES_USER', 'tork_admin')
    db_pass = os.environ.get('POSTGRES_PASSWORD', 'tork_db_pass_2026')

    print(f"Connecting to database {db_name} at {db_host}:{db_port} as {db_user}...")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_pass
    )
    conn.set_client_encoding('UTF8')
    cur = conn.cursor()

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
    ORDER BY sku ASC;
    """
    cur.execute(query)
    rows = cur.fetchall()

    catalog = []
    zone_counts = {}

    for row in rows:
        sku, name, category, product_type, system_code, color, current_price_kzt, description = row
        sku_str = str(sku).strip()
        zone = calculate_zone(product_type, system_code, name)
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

        price_val = float(current_price_kzt) if current_price_kzt is not None else 0.0

        item = {
            "sku": sku_str,
            "name": name.strip() if name else "",
            "category": category.strip() if category else "dispenser",
            "product_type": product_type.strip() if product_type else "",
            "system_code": system_code.strip() if system_code else "",
            "color": color.strip() if color else "none",
            "price": price_val,
            "image_url": f"/images/{sku_str}.png",
            "description": description.strip() if description else "",
            "zone": zone
        }
        catalog.append(item)

    cur.close()
    conn.close()

    output_path = root_dir / 'webapp' / 'products.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Successfully exported {len(catalog)} products to {output_path}")
    print("Zone breakdown:", zone_counts)

if __name__ == '__main__':
    main()
