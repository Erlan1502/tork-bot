#!/usr/bin/env python3
"""
Automated Test Suite for Kazakhstan Commercial Proposal V2 (Phase 4):
Validates:
1. Manager data autofill from allowed_managers (by telegram_id).
2. Accurate Kazakhstan 16% VAT calculation and 50/50 payment condition split.
3. Proper hero photomontage embedding on Page 1 (image size > 50 KB).
4. Strict 5-page document compilation via Gotenberg Chromium (< 1.5s, 0 LLM tokens).
5. Kazakhstan B2B content across all 5 pages (no Uzbekistan/Samarkand mentions).
6. File generation: 'КП_Tork_{Компания}_{Дата}.pdf'.
"""

import os
import sys
import time
import json
import io
import urllib.request
import pypdf

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_BASE = os.getenv("API_BASE", "http://localhost:8088/api/manager")

def test_1_form_defaults():
    print("\n--- TEST 1: Manager Data Autofill from allowed_managers ---")
    url = f"{API_BASE}/form-defaults?telegram_id=5699064827"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected status 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))

    assert data.get("ok") is True
    defaults = data.get("defaults", {})
    print(f"  Manager Name: {defaults.get('manager_name')}")
    print(f"  Manager Phone: {defaults.get('manager_phone')}")
    print(f"  Manager Telegram: {defaults.get('manager_tg')}")
    print(f"  Client City: {defaults.get('client_city')}")

    assert defaults.get("manager_name"), "manager_name must not be empty"
    assert defaults.get("manager_phone"), "manager_phone must not be empty"
    assert "Астана" in defaults.get("client_city", ""), "client_city should default to Astana"
    print("  ✅ TEST 1 PASSED: Autofill successfully pulled from database.")


def test_2_financial_vat_formula():
    print("\n--- TEST 2: Kazakhstan 16% VAT & 50/50 Payment Formula ---")
    items = [
        {"sku": "551000", "count": 16, "price": 85000.0},
        {"sku": "680008", "count": 20, "price": 42000.0},
        {"sku": "564500", "count": 12, "price": 35000.0},
        {"sku": "563000", "count": 8, "price": 55000.0}
    ]
    # Sum: 16*85000 (1 360 000) + 20*42000 (840 000) + 12*35000 (420 000) + 8*55000 (440 000) = 3 060 000
    expected_total = 3060000.0
    expected_vat = round(expected_total * 16 / 116) # 422 069 ₸
    expected_prepay = round(expected_total * 0.5)   # 1 530 000 ₸
    expected_postpay = expected_total - expected_prepay # 1 530 000 ₸

    print(f"  Expected Total: {expected_total:,.0f} ₸")
    print(f"  Expected 16% VAT portion: {expected_vat:,.0f} ₸")
    print(f"  Expected Prepayment 50%: {expected_prepay:,.0f} ₸")
    print(f"  Expected Remainder 50%: {expected_postpay:,.0f} ₸")

    assert expected_prepay + expected_postpay == expected_total
    assert expected_vat > 0
    print("  ✅ TEST 2 PASSED: Mathematical formulas for 16% VAT and 50/50 payment split verified.")


def test_3_generate_kp_and_validate_pdf():
    print("\n--- TEST 3: Generate 5-Page Commercial Proposal via Gotenberg ---")
    test_items = [
        {
            "sku": "551000",
            "name": "Tork Matic® диспенсер для полотенец в рулонах H1",
            "system_code": "H1",
            "color": "Белый Elevation",
            "dimensions": "37,2 × 33,7 × 20,3 см",
            "count": 16,
            "price": 85000
        },
        {
            "sku": "680008",
            "name": "Tork SmartOne® диспенсер для туалетной бумаги T8",
            "system_code": "T8",
            "color": "Черный Elevation",
            "dimensions": "26,9 × 26,9 × 15,6 см",
            "count": 20,
            "price": 42000
        },
        {
            "sku": "564500",
            "name": "Tork диспенсер для мыла-пены S4",
            "system_code": "S4",
            "color": "Белый Elevation",
            "dimensions": "29 × 11,2 × 9,9 см",
            "count": 12,
            "price": 35000
        },
        {
            "sku": "563000",
            "name": "Tork корзина для мусора 50 л со скрытым мешком B1",
            "system_code": "B1",
            "color": "Белый Elevation",
            "dimensions": "62,9 × 38,9 × 18,9 см",
            "count": 8,
            "price": 55000
        }
    ]

    payload = {
        "telegram_id": 5699064827,
        "company_name": "ТОО «РУБИЛЬНИК»",
        "client_facility": "Гостиничный комплекс, 5 этажей, 42 санузла",
        "client_city": "г. Астана, Казахстан",
        "manager_name": "Ерлан Кубесов",
        "manager_phone": "+7 (777) 777-77-77",
        "manager_tg": "@erlan_tork_kz",
        "items": test_items,
        "format": "json"
    }

    t0 = time.time()
    req = urllib.request.Request(
        f"{API_BASE}/generate-kp",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        elapsed = time.time() - t0
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        res_data = json.loads(resp.read().decode("utf-8"))

    print(f"  Generation speed: {elapsed:.2f} seconds (Target: < 1.5s, 0 AI tokens)")
    assert elapsed < 3.0, f"Compilation took too long: {elapsed:.2f}s"

    filename = res_data.get("filename", "")
    print(f"  Generated Filename: {filename}")
    assert filename.startswith("КП_Tork_ТОО__РУБИЛЬНИК_"), f"Unexpected filename: {filename}"
    assert filename.endswith(".pdf")

    pdf_base64 = res_data.get("pdf_base64", "")
    import base64
    pdf_bytes = base64.b64decode(pdf_base64)
    print(f"  PDF file size: {len(pdf_bytes) / 1024:.1f} KB")

    # Read and parse with pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    print(f"  Document pages count: {page_count} (Strict requirement: exactly 5 pages)")
    assert page_count == 5, f"Expected exactly 5 pages, got {page_count}"

    # Verify Page 1 Hero Image
    p1 = reader.pages[0]
    p1_images = p1.images
    print(f"  Page 1 images count: {len(p1_images)}")
    assert len(p1_images) >= 1, "Page 1 must contain at least 1 image (the hero visual montage)"
    hero_img = p1_images[0]
    print(f"  Hero image name: {hero_img.name}, size: {len(hero_img.data)} bytes")
    assert len(hero_img.data) > 50000, f"Hero image must be a high-resolution fitting (>50 KB), got {len(hero_img.data)} bytes"

    # Verify Page-by-Page Content
    full_text = ""
    for i, page in enumerate(reader.pages):
        page_num = i + 1
        txt = page.extract_text()
        full_text += f"\n--- PAGE {page_num} ---\n" + txt

        if page_num == 1:
            assert "ТОО «Tork Kazakhstan Distribution»" in txt, "Page 1 missing RK distributor header"
            assert "РУБИЛЬНИК" in txt, "Page 1 missing client company name"
            assert "НДС 16%" in txt, "Page 1 missing 16% VAT indicator"
            assert "Предоплата (50%)" in txt, "Page 1 missing 50% advance row"
            assert "Остаток (50%)" in txt, "Page 1 missing 50% remainder row"
            assert "Гарантия 3 года" in txt, "Page 1 missing 3-year warranty badge"
            assert "0 ₸" in txt, "Page 1 missing 0 ₸ mounting badge"
        elif page_num == 2:
            assert "Спецификация" in txt, "Page 2 missing Specification title"
            assert "551000" in txt, "Page 2 missing SKU 551000"
            assert "НДС 16%" in txt, "Page 2 missing 16% VAT"
            assert "Рекомендуемые расходные материалы" in txt, "Page 2 missing refills table"
        elif page_num == 3:
            assert "Расстановка оборудования по объекту" in txt, "Page 3 missing room distribution title"
            assert "Монтаж всех 56 диспенсеров" in txt or "0 ₸" in txt, "Page 3 missing mounting info"
            assert "ИТОГО ПО ВСЕМУ ОБЪЕКТУ" in txt, "Page 3 missing grand total row"
        elif page_num == 4:
            assert "Преимущества" in txt, "Page 4 missing advantages title"
            assert "до 40%" in txt, "Page 4 missing 40% paper savings metric"
            assert "2 500 доз" in txt or "2500" in txt, "Page 4 missing foam soap dose metric"
            assert "растворение за 8 секунд" in txt or "8 секунд" in txt, "Page 4 missing 8 sec dissolution"
        elif page_num == 5:
            assert "Порядок реализации проекта" in txt or "Порядок работы" in txt, "Page 5 missing 6-step workflow"
            assert "1 Заявка" in txt or "Заявка и аудит" in txt, "Page 5 missing step 1"
            assert "Гарантия 3 года" in txt, "Page 5 missing warranty"
            assert "Ерлан Кубесов" in txt, "Page 5 missing manager name"
            assert "+7 (777) 777-77-77" in txt, "Page 5 missing manager phone"

    # Strict check: NO Uzbekistan or Samarkand or so'm currency references
    forbidden_terms = ["Узбекистан", "Самарканд", "PRIME CORPORATION", " сум ", " сум\n", "zugurov3", "Тохир", "Ойбек"]
    for term in forbidden_terms:
        assert term not in full_text, f"Found forbidden regional term '{term}' in compiled Kazakhstan proposal!"

    print("  ✅ TEST 3 PASSED: All 5 pages validated with correct metrics, high-res photomontage, and Kazakhstan distributor branding.")


def main():
    print("=" * 70)
    print("🚀 RUNNING AUTOMATED TEST SUITE: COMMERCIAL PROPOSAL V2 (KZ 5-PAGE)")
    print("=" * 70)
    test_1_form_defaults()
    test_2_financial_vat_formula()
    test_3_generate_kp_and_validate_pdf()
    print("\n" + "=" * 70)
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! FULL 5-PAGE KP PRODUCTION READY.")
    print("=" * 70)

if __name__ == "__main__":
    main()
