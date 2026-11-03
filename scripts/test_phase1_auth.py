#!/usr/bin/env python3
"""
Test Suite for Phase 1: Access Control & Manager Whitelist
Tests workflow JSON schema, node connectivity, config files, and executes
the exact JS whitelist logic inside Node.js across various Telegram payloads.
"""

import json
import subprocess
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def test_config_files():
    print("[1/3] Testing Configuration Files...")
    
    # 1. Check .env.example
    with open(".env.example", "r", encoding="utf-8") as f:
        env_example = f.read()
    assert "ALLOWED_TELEGRAM_IDS=" in env_example, "ALLOWED_TELEGRAM_IDS not found in .env.example"
    print("  [OK] .env.example contains ALLOWED_TELEGRAM_IDS definition")
    
    # 2. Check docker-compose.yml
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        dc = f.read()
    assert "ALLOWED_TELEGRAM_IDS=${ALLOWED_TELEGRAM_IDS}" in dc, "ALLOWED_TELEGRAM_IDS not forwarded in docker-compose.yml"
    print("  [OK] docker-compose.yml forwards ALLOWED_TELEGRAM_IDS to n8n container")

def test_workflow_structure():
    print("\n[2/3] Testing Workflow Structure & Connections...")
    
    with open("workflows/tork_bot_workflow.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    wf = data[0] if isinstance(data, list) else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    conns = wf.get("connections", {})
    
    # Required nodes
    assert "Check Manager Whitelist" in nodes, "Check Manager Whitelist node missing"
    assert "Is User Allowed?" in nodes, "Is User Allowed? node missing"
    assert "Send Access Denied" in nodes, "Send Access Denied node missing"
    print("  [OK] All 3 access control nodes present in workflow")
    
    # Validate node types
    assert nodes["Check Manager Whitelist"]["type"] == "n8n-nodes-base.code"
    assert nodes["Is User Allowed?"]["type"] == "n8n-nodes-base.if"
    assert nodes["Send Access Denied"]["type"] == "n8n-nodes-base.telegram"
    print("  [OK] Node types match specifications")
    
    # Validate connections
    filter_conn = conns.get("Filter Private Chat Only", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Check Manager Whitelist" for c in filter_conn), \
        "Filter Private Chat Only must connect to Check Manager Whitelist"
    print("  [OK] Filter Private Chat Only -> Check Manager Whitelist")
    
    whitelist_conn = conns.get("Check Manager Whitelist", {}).get("main", [[]])[0]
    assert any(c.get("node") == "Is User Allowed?" for c in whitelist_conn), \
        "Check Manager Whitelist must connect to Is User Allowed?"
    print("  [OK] Check Manager Whitelist -> Is User Allowed?")
    
    is_allowed_main = conns.get("Is User Allowed?", {}).get("main", [])
    assert len(is_allowed_main) >= 2, "Is User Allowed? must have 2 output branches"
    
    true_branch = is_allowed_main[0]
    false_branch = is_allowed_main[1]
    
    assert any(c.get("node") == "Check Media Type" for c in true_branch), \
        "Output 0 (True) must connect to Check Media Type"
    print("  [OK] Is User Allowed? [True branch] -> Check Media Type")
    
    assert any(c.get("node") == "Send Access Denied" for c in false_branch), \
        "Output 1 (False) must connect to Send Access Denied"
    print("  [OK] Is User Allowed? [False branch] -> Send Access Denied")
    
    assert "Send Access Denied" not in conns or not conns["Send Access Denied"].get("main"), \
        "Send Access Denied must be a terminal node"
    print("  [OK] Send Access Denied is terminal (no unauthorized bypass)")

def test_whitelist_logic_execution():
    print("\n[3/3] Testing Whitelist Logic Execution in Node.js...")
    
    with open("workflows/tork_bot_workflow.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    wf = data[0] if isinstance(data, list) else data
    whitelist_node = next(n for n in wf["nodes"] if n["name"] == "Check Manager Whitelist")
    raw_js = whitelist_node["parameters"]["jsCode"]
    
    # Test cases to evaluate against the actual JS code
    test_cases = [
        {
            "name": "Authorized manager by userId",
            "env_allowed": "1001, 1002, 1003",
            "payload": {
                "message": {
                    "chat": {"id": 1001, "type": "private"},
                    "from": {"id": 1001, "first_name": "Erlan", "username": "erlan_mgr"},
                    "text": "/start"
                }
            },
            "expected_allowed": True,
            "expected_name": "Erlan"
        },
        {
            "name": "Unauthorized stranger rejected",
            "env_allowed": "1001, 1002, 1003",
            "payload": {
                "message": {
                    "chat": {"id": 9999, "type": "private"},
                    "from": {"id": 9999, "first_name": "Stranger", "username": "unknown_user"},
                    "text": "Hello"
                }
            },
            "expected_allowed": False,
            "expected_name": "Stranger"
        },
        {
            "name": "Authorized manager via callback query",
            "env_allowed": "1001, 1002, 1003",
            "payload": {
                "callback_query": {
                    "id": "cb123",
                    "from": {"id": 1002, "first_name": "Alibek", "last_name": "Manager"},
                    "message": {"chat": {"id": 1002, "type": "private"}},
                    "data": "select_h1"
                }
            },
            "expected_allowed": True,
            "expected_name": "Alibek Manager"
        },
        {
            "name": "Unauthorized stranger clicking callback query rejected",
            "env_allowed": "1001, 1002, 1003",
            "payload": {
                "callback_query": {
                    "id": "cb999",
                    "from": {"id": 8888, "first_name": "Hacker"},
                    "message": {"chat": {"id": 8888, "type": "private"}},
                    "data": "hack_attempt"
                }
            },
            "expected_allowed": False,
            "expected_name": "Hacker"
        },
        {
            "name": "Empty whitelist allows all (initial setup mode)",
            "env_allowed": "",
            "payload": {
                "message": {
                    "chat": {"id": 5555, "type": "private"},
                    "from": {"id": 5555, "first_name": "FirstTimer"},
                    "text": "/start"
                }
            },
            "expected_allowed": True,
            "expected_name": "FirstTimer"
        },
        {
            "name": "Delimiters formatting (spaces, semicolons, tabs)",
            "env_allowed": "111;  222\n333\t444",
            "payload": {
                "message": {
                    "chat": {"id": 333, "type": "private"},
                    "from": {"id": 333, "first_name": "Aigul"},
                    "text": "/start"
                }
            },
            "expected_allowed": True,
            "expected_name": "Aigul"
        }
    ]
    
    # Wrap JS in harness for node
    runner_script = f"""
const fs = require('fs');

const testCases = {json.dumps(test_cases)};

function runLogic(payload, allowedEnv) {{
    // Mock n8n context
    const $json = payload;
    const $input = {{ first: () => ({{ json: payload }}) }};
    const $ = () => ({{ first: () => ({{ json: payload }}) }});
    const $env = {{ ALLOWED_TELEGRAM_IDS: allowedEnv }};
    
    // Evaluate node jsCode
    {raw_js}
}}

let passed = 0;
for (const tc of testCases) {{
    const res = runLogic(tc.payload, tc.env_allowed);
    const item = res[0].json;
    
    if (item.auth.is_allowed !== tc.expected_allowed) {{
        console.error(`FAIL: ${{tc.name}} -> expected is_allowed=${{tc.expected_allowed}}, got ${{item.auth.is_allowed}}`);
        process.exit(1);
    }}
    if (tc.expected_name && item.auth.user_name !== tc.expected_name) {{
        console.error(`FAIL: ${{tc.name}} -> expected name=${{tc.expected_name}}, got ${{item.auth.user_name}}`);
        process.exit(1);
    }}
    console.log(`  [OK] ${{tc.name}} (is_allowed=${{item.auth.is_allowed}}, user="${{item.auth.user_name}}", id=${{item.auth.user_id}})`);
    passed++;
}}

console.log(`\nAll ${{passed}} Node.js simulation tests passed!`);
"""
    
    res = subprocess.run(["node", "-e", runner_script], capture_output=True, text=True)
    if res.returncode != 0:
        print("Node.js test execution error:")
        print(res.stderr)
        print(res.stdout)
        sys.exit(res.returncode)
    else:
        print(res.stdout.strip())

if __name__ == "__main__":
    try:
        test_config_files()
        test_workflow_structure()
        test_whitelist_logic_execution()
        print("\n==================================================")
        print("PHASE 1 COMPLETE: All tests passed successfully!")
        print("==================================================")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
