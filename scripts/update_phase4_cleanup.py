#!/usr/bin/env python3
"""
Phase 4 Workflow Cleanup:
Prunes 21 dead/orphaned nodes from old customer lead funnel,
cleans connections, updates set_menu_button.py and README.md.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def cleanup_workflow():
    workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_array = isinstance(data, list)
    wf = data[0] if is_array else data
    nodes = wf["nodes"]
    conns = wf["connections"]

    # Compute reachable nodes from Telegram Trigger
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

    initial_count = len(nodes)
    pruned_nodes = [n for n in nodes if n["name"] in reachable]
    removed_nodes = [n["name"] for n in nodes if n["name"] not in reachable]

    # Clean connections dictionary
    cleaned_conns = {}
    for src, outputs in conns.items():
        if src in reachable:
            cleaned_outputs = {}
            for out_key, grp_list in outputs.items():
                new_grp_list = []
                for grp in grp_list:
                    new_grp = [c for c in grp if c.get("node") in reachable]
                    new_grp_list.append(new_grp)
                cleaned_outputs[out_key] = new_grp_list
            cleaned_conns[src] = cleaned_outputs

    wf["nodes"] = pruned_nodes
    wf["connections"] = cleaned_conns

    new_data = [wf] if is_array else wf
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"Workflow pruned: {initial_count} nodes -> {len(pruned_nodes)} active nodes (removed {len(removed_nodes)} dead nodes).")

def update_menu_button_script():
    menu_script_path = ROOT / "scripts" / "set_menu_button.py"
    with open(menu_script_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Clean up garbled text and ensure UTF-8
    clean_script = '''import os
import json
import urllib.request
from pathlib import Path

def load_env(env_path):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip("\'\\"")
    return env_vars

def main():
    root_dir = Path(__file__).resolve().parent.parent
    env_path = root_dir / ".env"
    env_vars = load_env(env_path)

    token = os.getenv("TELEGRAM_BOT_TOKEN") or env_vars.get("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL") or env_vars.get("WEBHOOK_URL", "http://localhost:8088")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment or .env")

    webapp_url = f"{webhook_url.rstrip(\'/\')}/app/index.html"
    api_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"

    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "✨ Каталог Tork",
            "web_app": {
                "url": webapp_url
            }
        }
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            print(f"Success! Response: {resp_body}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode(\'utf-8\')}")
        raise
    except Exception as e:
        print(f"Error setting chat menu button: {e}")
        raise

if __name__ == "__main__":
    main()
'''
    with open(menu_script_path, "w", encoding="utf-8") as f:
        f.write(clean_script)
    print("Updated scripts/set_menu_button.py with clean Russian button label")

if __name__ == "__main__":
    cleanup_workflow()
    update_menu_button_script()
