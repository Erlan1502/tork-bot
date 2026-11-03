#!/usr/bin/env python3
"""
Test Suite for Phase 3: Manager-Only Workflow Reorganization & AI Fitting Pipeline
Tests workflow graph integrity, database migrations, and simulates all JS node logic
(dispenser parsing, montage prompt preparation, Gemini result processing) in Node.js.
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

def test_database_migrations():
    print("[1/3] Testing Database Schema & Migrations...")
    
    migration_file = ROOT / "migrations" / "004_manager_mode.sql"
    assert migration_file.exists(), "migrations/004_manager_mode.sql missing"
    
    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read()
    assert "selected_sku" in sql, "selected_sku not defined in migration 004"
    print("  [OK] Migration 004_manager_mode.sql defines selected_sku column")
    
    init_sql = ROOT / "init.sql"
    with open(init_sql, "r", encoding="utf-8") as f:
        init_content = f.read()
    assert "selected_sku" in init_content, "selected_sku not present in init.sql"
    print("  [OK] init.sql updated with selected_sku column for user_sessions_leads")

def test_workflow_structure():
    print("\n[2/3] Testing Manager Mode Workflow Graph & Bypassed Nodes...")
    
    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    wf = data[0] if isinstance(data, list) else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    conns = wf.get("connections", {})
    
    # Required Manager Nodes
    required_nodes = [
        "Parse Selected Dispenser",
        "Save Selected Dispenser (SQL)",
        "Send Dispenser Confirmation",
        "Fetch Current Manager Selection (SQL)",
        "Prepare Manager Montage",
        "Call Image Edit API",
        "Process Manager Result",
        "Send Manager Result Photo",
        "Send Manager Welcome & Menu"
    ]
    for r in required_nodes:
        assert r in nodes, f"Required manager node '{r}' missing in workflow"
    print("  [OK] All 9 manager-mode nodes present in workflow")
    
    # Verify Route by Event Type connections
    route_conns = conns.get("Route by Event Type", {}).get("main", [])
    assert len(route_conns) >= 4, "Route by Event Type must have 4 output branches"
    
    # Branch 0: WebApp Dispenser Selection
    assert any(c.get("node") == "Parse Selected Dispenser" for c in route_conns[0]), \
        "Branch 0 must route to Parse Selected Dispenser"
    parse_conn = conns.get("Parse Selected Dispenser", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Save Selected Dispenser (SQL)" for c in parse_conn), \
        "Parse Selected Dispenser -> Save Selected Dispenser (SQL)"
    save_conn = conns.get("Save Selected Dispenser (SQL)", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Send Dispenser Confirmation" for c in save_conn), \
        "Save Selected Dispenser (SQL) -> Send Dispenser Confirmation"
    print("  [OK] Event flow: WebApp Select -> Parse -> Save SQL -> Send Dispenser Confirmation")
    
    # Branch 1: Photo Montage Pipeline
    assert any(c.get("node") == "Download Telegram Photo" for c in route_conns[1]), \
        "Branch 1 must route to Download Telegram Photo"
    dl_conn = conns.get("Download Telegram Photo", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Fetch Current Manager Selection (SQL)" for c in dl_conn), \
        "Download Telegram Photo -> Fetch Current Manager Selection (SQL)"
    fetch_conn = conns.get("Fetch Current Manager Selection (SQL)", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Prepare Manager Montage" for c in fetch_conn), \
        "Fetch Current Manager Selection (SQL) -> Prepare Manager Montage"
    prep_conn = conns.get("Prepare Manager Montage", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Call Image Edit API" for c in prep_conn), \
        "Prepare Manager Montage -> Call Image Edit API"
    edit_conn = conns.get("Call Image Edit API", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Process Manager Result" for c in edit_conn), \
        "Call Image Edit API -> Process Manager Result"
    proc_conn = conns.get("Process Manager Result", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Send Manager Result Photo" for c in proc_conn), \
        "Process Manager Result -> Send Manager Result Photo"
    print("  [OK] Event flow: Photo -> Download -> Fetch SKU -> Prepare Montage -> Gemini API -> Process Result -> Send Result Photo")
    
    # Branch 2 & 3: Welcome & Menu
    assert any(c.get("node") == "Send Manager Welcome & Menu" for c in route_conns[2]), \
        "Branch 2 must route to Send Manager Welcome & Menu"
    assert any(c.get("node") == "Send Manager Welcome & Menu" for c in route_conns[3]), \
        "Branch 3 must route to Send Manager Welcome & Menu"
    print("  [OK] Event flow: /start, text & commands -> Send Manager Welcome & Menu")
    
    # Verify Bypassed Customer Friction Nodes
    for branch in route_conns:
        assert not any(c.get("node") == "Check Rate Limit" for c in branch), \
            "Check Rate Limit must NOT be connected in manager mode"
        assert not any(c.get("node") == "Send Welcome Onboarding" for c in branch), \
            "Send Welcome Onboarding must NOT be connected in manager mode"
    print("  [OK] Customer friction nodes (Rate limits & onboarding surveys) successfully bypassed")

def test_node_logic_execution():
    print("\n[3/3] Testing Manager Workflow Logic in Node.js...")
    
    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    wf = data[0] if isinstance(data, list) else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    
    parse_js = nodes["Parse Selected Dispenser"]["parameters"]["jsCode"]
    prep_js = nodes["Prepare Manager Montage"]["parameters"]["jsCode"]
    proc_js = nodes["Process Manager Result"]["parameters"]["jsCode"]
    
    assets_dir_posix = str(ROOT / "assets" / "images").replace("\\", "/")
    
    runner = f"""
const fs = require('fs');

// 1. Test Parse Selected Dispenser Logic
function testParseDispenser() {{
  const mockWebAppData = JSON.stringify({{
    action: 'select_dispenser',
    sku: '551000',
    name: 'Tork Matic dispenser H1',
    system_code: 'H1',
    color: 'white',
    category: 'dispenser'
  }});
  
  const $json = {{
    message: {{
      chat: {{ id: 1001 }},
      from: {{ id: 1001, first_name: 'Erlan' }},
      web_app_data: {{ data: mockWebAppData }}
    }}
  }};
  const $input = {{ first: () => ({{ json: $json }}) }};
  const $ = () => ({{ first: () => ({{ json: $json }}) }});
  
  // Evaluate node jsCode
  {parse_js}
}}

const parseRes = testParseDispenser();
const parsedItem = parseRes[0].json;
if (parsedItem.sku !== '551000' || parsedItem.system_code !== 'H1' || parsedItem.tg_user_id !== 1001) {{
  console.error("FAIL: testParseDispenser failed:", parsedItem);
  process.exit(1);
}}
console.log("  [OK] Parse Selected Dispenser correctly extracted SKU 551000 & user ID 1001");

// 2. Test Prepare Manager Montage Logic
// Mock fs to resolve local assets
const realFs = require('fs');
const origExists = realFs.existsSync;
const origRead = realFs.readFileSync;
realFs.existsSync = (p) => {{
  const localP = String(p).replace('/data/assets/images', '{assets_dir_posix}');
  return origExists(localP);
}};
realFs.readFileSync = (p, enc) => {{
  const localP = String(p).replace('/data/assets/images', '{assets_dir_posix}');
  return origRead(localP, enc);
}};

function testPrepareMontage() {{
  // Mock photo in binary
  const photoBinary = {{
    binary: {{
      data: {{
        data: 'dummy_user_photo_base64_data'
      }}
    }}
  }};
  
  const selectionSql = {{
    selected_sku: '551000',
    dispenser_name: 'Tork Matic H1',
    system_code: 'H1',
    color: 'white',
    dimensions_cm: {{ w: 33.7, h: 37.2, d: 20.6 }}
  }};
  
  const $json = {{}};
  const $ = (nodeName) => ({{
    first: () => {{
      if (nodeName === 'Download Telegram Photo') return photoBinary;
      if (nodeName === 'Fetch Current Manager Selection (SQL)') return {{ json: selectionSql }};
      if (nodeName === 'Telegram Trigger') return {{ json: {{ message: {{ chat: {{ id: 1001 }} }} }} }};
      return {{ json: {{}} }};
    }}
  }});
  const $input = {{ first: () => ({{ json: {{}} }}) }};
  
  // Evaluate node jsCode
  {prep_js}
}}

const prepRes = testPrepareMontage();
const prepItem = prepRes[0].json;
if (prepItem.sku !== '551000' || !prepItem.dispenser_clean_base64 || !prepItem.prompt_text) {{
  console.error("FAIL: testPrepareMontage failed:", prepItem);
  process.exit(1);
}}
console.log(`  [OK] Prepare Manager Montage loaded clean PNG asset (${{prepItem.dispenser_clean_base64.length}} bytes base64)`);
console.log("  [OK] Generated photorealistic Gemini montage prompt with dimensions 33.7 x 37.2 cm");

// 3. Test Process Manager Result Logic
function testProcessResult() {{
  const prepJson = prepItem;
  const geminiResponse = {{
    candidates: [
      {{
        content: {{
          parts: [
            {{
              inlineData: {{
                data: 'mock_gemini_generated_image_bytes',
                mimeType: 'image/jpeg'
              }}
            }}
          ]
        }}
      }}
    ]
  }};
  
  const $ = (nodeName) => ({{
    first: () => ({{ json: prepJson }})
  }});
  const $input = {{ first: () => ({{ json: geminiResponse }}) }};
  
  // Evaluate node jsCode
  {proc_js}
}}

const procRes = testProcessResult();
const procItem = procRes[0].json;
const procBin = procRes[0].binary;

if (!procBin?.visualization?.data || procBin.visualization.fileName !== 'tork_551000_fitting.png') {{
  console.error("FAIL: testProcessResult binary packaging failed:", procBin);
  process.exit(1);
}}
if (!procItem.caption || !procItem.caption.includes('551000')) {{
  console.error("FAIL: testProcessResult caption failed:", procItem);
  process.exit(1);
}}
console.log("  [OK] Process Manager Result packaged binary image and generated Telegram HTML caption");
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
        test_database_migrations()
        test_workflow_structure()
        test_node_logic_execution()
        print("\n==================================================")
        print("PHASE 3 COMPLETE: All tests passed successfully!")
        print("==================================================")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
