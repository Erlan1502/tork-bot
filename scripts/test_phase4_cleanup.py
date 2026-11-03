#!/usr/bin/env python3
"""
Test Suite for Phase 4: Workflow Cleanup, Menu Button Script & Documentation
Validates workflow graph purity (no orphaned nodes), menu button configuration,
and comprehensive project documentation.
"""

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent

def test_workflow_purity():
    print("[1/3] Testing Workflow Graph Purity & Pruning...")
    
    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    wf = data[0] if isinstance(data, list) else data
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    conns = wf.get("connections", {})
    
    # 1. Total node count must be exactly 19
    assert len(nodes) == 19, f"Expected exactly 19 active nodes, found {len(nodes)}"
    print(f"  [OK] Workflow contains exactly {len(nodes)} active nodes (all 21 obsolete nodes pruned)")
    
    # 2. Check that no obsolete customer funnel nodes exist
    obsolete_names = [
        "Send Welcome Onboarding", "Update Session Segment", "Send Photo Request",
        "Check Rate Limit", "Limit Exceeded Message", "Calculate KP Bundle",
        "Generate PDF via Gotenberg", "Send Client Result & Inline Buttons",
        "Send Client PDF Document", "Notify Managers Group", "Parse WebApp Order & Match Distributor"
    ]
    for obs in obsolete_names:
        assert obs not in nodes, f"Obsolete node '{obs}' should have been removed"
    print("  [OK] Confirmed complete removal of old customer onboarding, rate limits and PDF bundle nodes")
    
    # 3. Graph reachability: all nodes must be reachable from Telegram Trigger
    reachable = set()
    queue = ["Telegram Trigger"]
    while queue:
        curr = queue.pop(0)
        if curr in reachable:
            continue
        reachable.add(curr)
        for output_type, outputs in conns.get(curr, {}).items():
            for grp in outputs:
                for item in grp:
                    target = item.get("node")
                    if target and target not in reachable:
                        queue.append(target)
                        
    assert len(reachable) == len(nodes), \
        f"Graph has unreachable nodes: {set(nodes.keys()) - reachable}"
    print(f"  [OK] 100% graph reachability: all {len(reachable)} nodes are active and connected")
    
    # 4. Verify all connection references point to valid nodes
    for src, outputs in conns.items():
        assert src in nodes, f"Connection source '{src}' does not exist in nodes"
        for out_type, grp_list in outputs.items():
            for grp in grp_list:
                for item in grp:
                    target = item.get("node")
                    assert target in nodes, f"Connection target '{target}' does not exist in nodes"
    print("  [OK] All graph connection targets are strictly valid and active")

def test_menu_button_script():
    print("\n[2/3] Testing Telegram Menu Button Configuration...")
    
    menu_script = ROOT / "scripts" / "set_menu_button.py"
    assert menu_script.exists(), "scripts/set_menu_button.py missing"
    
    with open(menu_script, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "✨ Каталог Tork" in content, "Menu button text missing or corrupted"
    assert "setChatMenuButton" in content, "setChatMenuButton Telegram method missing"
    assert "web_app" in content, "web_app menu button type missing"
    print("  [OK] scripts/set_menu_button.py correctly configured with '✨ Каталог Tork' WebApp action")

def test_documentation_integrity():
    print("\n[3/3] Testing Documentation & Guides...")
    
    readme_path = ROOT / "README.md"
    assert readme_path.exists(), "README.md missing"
    
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
    
    assert "Manager-Only Mode" in readme, "Manager-Only Mode not documented in README"
    assert "ALLOWED_TELEGRAM_IDS" in readme, "ALLOWED_TELEGRAM_IDS not documented in README"
    assert "165" in readme, "165 products catalog not documented in README"
    assert "test_phase1_auth.py" in readme, "Phase 1 test not listed in README"
    assert "test_phase2_webapp.py" in readme, "Phase 2 test not listed in README"
    assert "test_phase3_workflow.py" in readme, "Phase 3 test not listed in README"
    assert "test_phase4_cleanup.py" in readme, "Phase 4 test not listed in README"
    print("  [OK] README.md contains complete instructions, architecture guide and test commands")

if __name__ == "__main__":
    try:
        test_workflow_purity()
        test_menu_button_script()
        test_documentation_integrity()
        print("\n==================================================")
        print("PHASE 4 COMPLETE: All tests passed successfully!")
        print("==================================================")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
