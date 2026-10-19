import psycopg2
import json

conn = psycopg2.connect(
    dbname="tork_bot_db",
    user="tork_admin",
    password="tork_db_pass_2026",
    host="localhost",
    port=5432
)
cur = conn.cursor()
cur.execute('SELECT "executionId", data FROM execution_data ORDER BY "executionId" DESC LIMIT 1;')
row = cur.fetchone()
if row:
    exec_id, raw_data = row
    print("Execution ID:", exec_id)
    try:
        parsed = json.loads(raw_data)
        result_data = parsed.get("resultData", {})
        error_info = result_data.get("error")
        print("Top-level error:", error_info)
        last_node = result_data.get("lastNodeExecuted")
        print("Last node executed:", last_node)
        # Check runData of each node
        run_data = result_data.get("runData", {})
        for node_name, runs in run_data.items():
            for r in runs:
                if "error" in r:
                    print(f"Node '{node_name}' error:", r["error"])
    except Exception as e:
        print("Error parsing data:", e)
        print("Raw prefix:", str(raw_data)[:1000])

cur.close()
conn.close()
