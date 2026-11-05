#!/usr/bin/env python3
"""
Syncs the complete, up-to-date workflow (including Presentation & Commercial Proposal buttons)
from workflows/tork_bot_workflow.json into n8n's workflow_entity and workflow_history tables.
"""
import json
import os
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
workflow_path = ROOT / "workflows" / "tork_bot_workflow.json"

if not workflow_path.exists():
    print(f"❌ Workflow file not found at: {workflow_path}")
    sys.exit(1)

with open(workflow_path, "r", encoding="utf-8") as f:
    wf = json.load(f)
    if isinstance(wf, list):
        wf = wf[0]

nodes_json = json.dumps(wf.get("nodes", []), ensure_ascii=False)
conns_json = json.dumps(wf.get("connections", {}), ensure_ascii=False)

# Try python psycopg2 first
conn = None
for port in [5432, 5433]:
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=port,
            user=os.getenv("POSTGRES_USER", "tork_admin"),
            password=os.getenv("POSTGRES_PASSWORD", "supersecret_tork_kz_pass"),
            dbname=os.getenv("POSTGRES_DB", "tork_bot_db"),
            connect_timeout=3
        )
        print(f"Connected to PostgreSQL on port {port}")
        break
    except Exception:
        pass

if conn:
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workflow_entity 
                SET nodes = %s::json, connections = %s::json, "updatedAt" = NOW() 
                WHERE id = 'sHnoGT842oAJacFu';

                UPDATE workflow_history 
                SET nodes = %s::json, connections = %s::json, "updatedAt" = NOW() 
                WHERE "workflowId" = 'sHnoGT842oAJacFu' OR "versionId" = '19f66501-b1fb-45e1-9d90-0c4add4f89a7';
            """, (nodes_json, conns_json, nodes_json, conns_json))
            conn.commit()
            print("✅ Successfully updated workflow_entity and workflow_history via psycopg2!")
    finally:
        conn.close()
else:
    # Fallback to docker exec psql
    import subprocess
    sql = f"""
    UPDATE workflow_entity 
    SET nodes = $n${nodes_json}$n$::json, 
        connections = $c${conns_json}$c$::json, 
        "updatedAt" = NOW() 
    WHERE id = 'sHnoGT842oAJacFu';

    UPDATE workflow_history 
    SET nodes = $n${nodes_json}$n$::json, 
        connections = $c${conns_json}$c$::json, 
        "updatedAt" = NOW() 
    WHERE "workflowId" = 'sHnoGT842oAJacFu' OR "versionId" = '19f66501-b1fb-45e1-9d90-0c4add4f89a7';
    """
    cmd = ["sudo", "docker", "exec", "-i", "tork_postgres", "psql", "-U", "tork_admin", "-d", "tork_bot_db"]
    proc = subprocess.run(cmd, input=sql.encode("utf-8"), capture_output=True)
    if proc.returncode == 0:
        print("✅ Successfully updated workflow_entity and workflow_history via docker psql!")
    else:
        # Try without sudo for environments where user is in docker group
        cmd_nosudo = ["docker", "exec", "-i", "tork_postgres", "psql", "-U", "tork_admin", "-d", "tork_bot_db"]
        proc2 = subprocess.run(cmd_nosudo, input=sql.encode("utf-8"), capture_output=True)
        if proc2.returncode == 0:
            print("✅ Successfully updated workflow_entity and workflow_history via docker psql (no sudo)!")
        else:
            print("❌ Failed to update database:", proc.stderr.decode(errors="ignore"))
            sys.exit(1)

print("🎉 Workflow synchronized with all 3 buttons: КП, Презентация, Каталог!")
