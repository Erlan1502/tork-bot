import json
import os
from collections import Counter

def main():
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../webapp/products.json"))
    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"Total products in catalog: {len(products)}")
    
    categories = Counter(p.get("category") for p in products)
    print("\n--- Categories (Функциональные зоны) ---")
    for cat, cnt in categories.items():
        print(f"  • {cat}: {cnt} SKU")

    systems = Counter(p.get("system_code") for p in products)
    print(f"\n--- System Codes (Всего систем: {len(systems)}) ---")
    for sys_code, cnt in sorted(systems.items()):
        dispensers = sum(1 for p in products if p.get("system_code") == sys_code and p.get("category") == "dispenser")
        refills = sum(1 for p in products if p.get("system_code") == sys_code and p.get("category") == "refill")
        print(f"  • {sys_code:6s}: {cnt:2d} SKU (Диспенсеров: {dispensers}, Расходников: {refills})")

    product_types = Counter(p.get("product_type") for p in products)
    print("\n--- Product Types (Типы продукции) ---")
    for pt, cnt in product_types.items():
        print(f"  • {pt}: {cnt} SKU")

if __name__ == "__main__":
    main()

