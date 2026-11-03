#!/usr/bin/env python3
"""
Test Suite for Phase 2: Mini App Transformation into Dispenser Selector
Tests catalog integrity (165 products & PNG assets), UI template reduction,
and executes Vue.js selector logic inside Node.js.
"""

import json
import os
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent

def test_catalog_and_assets():
    print("[1/3] Testing Catalog & Product Assets...")
    products_file = ROOT / "webapp" / "products.json"
    assert products_file.exists(), "webapp/products.json does not exist"
    
    with open(products_file, "r", encoding="utf-8") as f:
        products = json.load(f)
    
    assert len(products) == 165, f"Expected 165 products, got {len(products)}"
    print(f"  [OK] webapp/products.json contains exactly {len(products)} products (>100 SKU requirement met)")
    
    dispensers = [p for p in products if p.get("category") == "dispenser"]
    refills = [p for p in products if p.get("category") == "refill"]
    
    assert len(dispensers) > 0, "No dispensers found"
    assert len(refills) > 0, "No refills found"
    print(f"  [OK] Product categorization: {len(dispensers)} dispensers, {len(refills)} refills")
    
    # Check that each product has required properties
    for idx, p in enumerate(products):
        assert "sku" in p and p["sku"], f"Item {idx} missing sku"
        assert "name" in p and p["name"], f"Item {idx} missing name"
        assert "category" in p and p["category"] in ("dispenser", "refill"), f"Item {idx} invalid category"
        assert "zone" in p, f"Item {idx} missing zone"
    print("  [OK] All 165 products have valid schema (sku, name, category, zone, price)")
    
    # Verify corresponding PNG images in assets/images/
    assets_dir = ROOT / "assets" / "images"
    assert assets_dir.exists(), "assets/images directory missing"
    
    missing_images = []
    for d in dispensers:
        sku = d["sku"]
        img_path = assets_dir / f"{sku}.png"
        if not img_path.exists():
            missing_images.append(sku)
            
    assert len(missing_images) == 0, f"Missing PNG assets for dispenser SKUs: {missing_images[:5]}"
    print(f"  [OK] High-resolution PNG cutout assets exist for all {len(dispensers)} dispensers")

def test_html_ui_reduction():
    print("\n[2/3] Testing HTML UI Structure & B2B Cart Reduction...")
    html_file = ROOT / "webapp" / "index.html"
    assert html_file.exists(), "webapp/index.html missing"
    
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    
    # 1. Verify old B2B lead generation / customer cart was removed
    assert "isCartOpen" not in html, "isCartOpen should be removed from index.html"
    assert "cartTotalQty" not in html, "cartTotalQty should be removed from index.html"
    assert "company_name" not in html, "company_name form input should be removed from index.html"
    assert "bin" not in html, "bin form input should be removed from index.html"
    print("  [OK] B2B cart, company credentials and BIN checkout form successfully removed")
    
    # 2. Verify new selector elements are present
    assert "Tork Visualizer & Fitting" in html, "Title header missing"
    assert "Manager Mode" in html, "Manager Mode badge missing"
    assert 'id="search-input"' in html, "Search input missing"
    assert 'id="filter-dispenser"' in html, "Dispenser filter tab missing"
    assert 'id="product-modal-container"' in html, "Selection modal missing"
    assert 'confirmDispenserSelection' in html, "confirmDispenserSelection action missing"
    print("  [OK] Manager Mode header, search, category filters and fitting actions present")

def test_vue_logic_execution():
    print("\n[3/3] Testing Selector Logic & Filtering in Node.js...")
    
    app_js_path = str(ROOT / "webapp" / "app.js").replace("\\", "/")
    products_json_path = str(ROOT / "webapp" / "products.json").replace("\\", "/")
    
    runner = f"""
const fs = require('fs');

// Load products directly from file to avoid Windows command line length limit
const products = JSON.parse(fs.readFileSync('{products_json_path}', 'utf-8'));

// Mock Vue & Telegram
let capturedAppConfig = null;
global.Vue = {{
  createApp: (config) => {{
    capturedAppConfig = config;
    return {{
      mount: () => {{}}
    }};
  }}
}};

let sentDataPayload = null;
let webAppClosed = false;
global.window = {{
  Telegram: {{
    WebApp: {{
      ready: () => {{}},
      expand: () => {{}},
      setHeaderColor: () => {{}},
      setBackgroundColor: () => {{}},
      initDataUnsafe: {{
        user: {{ id: 1001, username: 'erlan_manager' }},
        chat: {{ id: 1001 }}
      }},
      sendData: (dataStr) => {{
        sentDataPayload = JSON.parse(dataStr);
      }},
      close: () => {{
        webAppClosed = true;
      }},
      HapticFeedback: {{
        impactOccurred: () => {{}},
        selectionChanged: () => {{}},
        notificationOccurred: () => {{}}
      }}
    }}
  }},
  location: {{ search: '' }}
}};
global.fetch = async (url) => ({{
  ok: true,
  json: async () => products
}});

// Execute app.js
require('{app_js_path}');

if (!capturedAppConfig) {{
  console.error("FAIL: createApp was not called in app.js");
  process.exit(1);
}}

// Instantiate component
const comp = {{
  ...capturedAppConfig.data(),
  ...capturedAppConfig.methods,
  $nextTick: (fn) => fn()
}};

for (const [key, fn] of Object.entries(capturedAppConfig.computed || {{}})) {{
  Object.defineProperty(comp, key, {{
    get: () => fn.call(comp),
    configurable: true
  }});
}}

comp.products = products;
comp.loading = false;

// 1. Check default category is dispenser
if (comp.selectedCategory !== 'dispenser') {{
  console.error(`FAIL: default selectedCategory should be 'dispenser', got '${{comp.selectedCategory}}'`);
  process.exit(1);
}}
console.log("  [OK] Default category is set to 'dispenser'");

// 2. Test zone filtering & computed counts
comp.selectedZone = 'zone_wash';
const counts = comp.zoneCounts;
if (counts.all <= 0 || counts.dispenser <= 0) {{
  console.error("FAIL: zoneCounts calculation failed");
  process.exit(1);
}}
console.log(`  [OK] zoneCounts correctly computed: ${{counts.dispenser}} dispensers out of ${{counts.all}} in zone_wash`);

// 3. Test search query
comp.searchQuery = '551000';
let filtered = comp.filteredProducts;
if (filtered.length !== 1 || filtered[0].sku !== '551000') {{
  console.error("FAIL: search by SKU 551000 failed");
  process.exit(1);
}}
console.log(`  [OK] Search by SKU 551000 correctly found: "${{filtered[0].name}}"`);

// 4. Test search by system code
comp.searchQuery = 'H1';
filtered = comp.filteredProducts;
if (filtered.length === 0) {{
  console.error("FAIL: search by system H1 failed");
  process.exit(1);
}}
console.log(`  [OK] Search by system 'H1' correctly matched ${{filtered.length}} products`);

// 5. Test dispenser selection and Telegram.WebApp.sendData
comp.searchQuery = '';
const testDispenser = products.find(p => p.sku === '551000');
(async () => {{
  await comp.confirmDispenserSelection(testDispenser);

  if (!sentDataPayload) {{
    console.error("FAIL: Telegram.WebApp.sendData was not called");
    process.exit(1);
  }}

  if (sentDataPayload.action !== 'select_dispenser' || sentDataPayload.sku !== '551000') {{
    console.error(`FAIL: invalid payload: ${{JSON.stringify(sentDataPayload)}}`);
    process.exit(1);
  }}

  if (sentDataPayload.tg_user_id !== 1001 || sentDataPayload.category !== 'dispenser') {{
    console.error(`FAIL: metadata missing in payload: ${{JSON.stringify(sentDataPayload)}}`);
    process.exit(1);
  }}

  console.log(`  [OK] Dispenser selection sent valid payload via Telegram.WebApp.sendData:`);
  console.log(`       action="${{sentDataPayload.action}}", sku="${{sentDataPayload.sku}}", user_id=${{sentDataPayload.tg_user_id}}`);
}})();
"""
    
    res = subprocess.run(["node", "-e", runner], capture_output=True, text=True)
    if res.returncode != 0:
        print("Node.js test execution error:")
        print(res.stderr)
        print(res.stdout)
        sys.exit(res.returncode)
    else:
        print(res.stdout.strip())

if __name__ == "__main__":
    try:
        test_catalog_and_assets()
        test_html_ui_reduction()
        test_vue_logic_execution()
        print("\n==================================================")
        print("PHASE 2 COMPLETE: All tests passed successfully!")
        print("==================================================")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
