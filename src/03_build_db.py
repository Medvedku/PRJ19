import json
import os
import tomllib
from pathlib import Path
import duckdb
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# SETUP & ENCRYPTED CONNECTION
# ------------------------------------------------------------------------------
print("=== INITIALIZING ENCRYPTED DATABASE BUILD ===")

# Load environment variables (.env)
load_dotenv()
db_pass = os.getenv("DB_PASS")

if not db_pass:
    raise ValueError("Missing 'DB_PASS' environment variable in .env file.")

# Load configuration paths
with open("config.toml", "rb") as f:
    config = tomllib.load(f)

mapping_path = Path(config["paths"]["schema_mapping"])
ndjson_path = Path(config["paths"]["download_dir"]) / "PRJ-19_flattened.ndjson"
db_dir = Path(config["paths"]["db_dir"])
db_path = db_dir / "PRJ-19.duckdb"

db_dir.mkdir(parents=True, exist_ok=True)

with open(mapping_path, "r", encoding="utf-8") as f:
    schema_mapping = json.load(f)

print(f"Target Database File: {db_path.resolve()}")
print(f"Schema Mapping Path:  {mapping_path.resolve()}")
print(f"Flattened NDJSON:     {ndjson_path.resolve()}")

# Connect in-memory, ATTACH encrypted DB, and set context
con = duckdb.connect()
con.execute(f"ATTACH '{db_path}' AS db (ENCRYPTION_KEY '{db_pass}');")
con.execute("USE db;")
print("--> Encrypted database attached and set as active context.\n")

# ------------------------------------------------------------------------------
# STEP 1: CREATE HUBS TABLE
# ------------------------------------------------------------------------------
print("=== STEP 1: CREATING & POPULATING HUBS TABLE ===")

con.execute("DROP TABLE IF EXISTS hubs;")

con.execute(
    """
    CREATE TABLE hubs (
        meta_uuid UBIGINT PRIMARY KEY,
        sn INT,
        span INT,
        sensors INT[]
    );
"""
)

hub_records = [
    (
        int(uuid_str),
        data["SN"],
        data["Span"],
        sorted([int(s) for s in data["sensors"].keys()]),
    )
    for uuid_str, data in schema_mapping.items()
]

con.executemany(
    """
    INSERT INTO hubs (meta_uuid, sn, span, sensors)
    VALUES (?, ?, ?, ?);
""",
    hub_records,
)

print(f"Successfully inserted {len(hub_records)} hubs.")
print("Hubs summary:")
print(con.execute("SELECT meta_uuid, sn, span, sensors FROM hubs ORDER BY span").df())
print()

# ------------------------------------------------------------------------------
# STEP 2: CREATE SENSORS TABLE
# ------------------------------------------------------------------------------
print("=== STEP 2: CREATING & POPULATING SENSORS TABLE ===")

con.execute("DROP TABLE IF EXISTS sensors;")

con.execute(
    """
    CREATE TABLE sensors (
        sensor_id INT PRIMARY KEY,
        meta_uuid UBIGINT REFERENCES hubs(meta_uuid),
        position INT,
        type VARCHAR,
        color VARCHAR,
        probes VARCHAR[],
        tare_pv0 DOUBLE,
        tare_pv1 DOUBLE,
        tare_pv2 DOUBLE,
        tare_pv3 DOUBLE
    );
"""
)

sensor_records = []
for uuid_str, hub_data in schema_mapping.items():
    meta_uuid = int(uuid_str)
    for sensor_id_str, sensor_info in hub_data["sensors"].items():
        sensor_id = int(sensor_id_str)
        
        # Parse position as INT (handles blank strings safely)
        pos_val = sensor_info.get("position")
        position = int(pos_val) if pos_val is not None and str(pos_val).isdigit() else None

        s_type = sensor_info.get("type")
        color = sensor_info.get("color")
        probes = sensor_info.get("probes", [])

        tare_dict = sensor_info.get("tare") or {}
        tare_pv0 = tare_dict.get("pv0")
        tare_pv1 = tare_dict.get("pv1")
        tare_pv2 = tare_dict.get("pv2")
        tare_pv3 = tare_dict.get("pv3")

        sensor_records.append(
            (
                sensor_id,
                meta_uuid,
                position,
                s_type,
                color,
                probes,
                tare_pv0,
                tare_pv1,
                tare_pv2,
                tare_pv3,
            )
        )

sensor_records.sort(key=lambda x: x[0])

con.executemany(
    """
    INSERT INTO sensors (
        sensor_id, meta_uuid, position, type, color, probes, 
        tare_pv0, tare_pv1, tare_pv2, tare_pv3
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
""",
    sensor_records,
)

print(f"Successfully inserted {len(sensor_records)} sensors.")
print("Sensors sample (First 10):")
print(con.execute("SELECT * FROM sensors ORDER BY sensor_id LIMIT 10").df())
print()

# ------------------------------------------------------------------------------
# STEP 3: CREATE DYNAMIC MEASUREMENT TABLES
# ------------------------------------------------------------------------------
print("=== STEP 3: CREATING MEASUREMENT TABLES PER SPAN ===")

hubs = con.execute("SELECT span, meta_uuid, sensors FROM hubs ORDER BY span").fetchall()

for span, meta_uuid, sensor_ids in hubs:
    table_name = f"measurements_span{span}"
    
    con.execute(f"DROP TABLE IF EXISTS {table_name};")
    
    column_defs = [
        "timestamp TIMESTAMP PRIMARY KEY",
        "voltage FLOAT"
    ]
    
    placeholders = ",".join("?" * len(sensor_ids))
    sensor_info = con.execute(
        f"SELECT sensor_id, probes FROM sensors WHERE sensor_id IN ({placeholders}) ORDER BY sensor_id",
        sensor_ids
    ).fetchall()
    
    for s_id, probes in sensor_info:
        for probe in probes:
            column_defs.append(f"values_{s_id}_{probe} FLOAT")
            
    create_query = f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(column_defs) + "\n);"
    con.execute(create_query)
    print(f" -> Created table: {table_name} ({len(column_defs)} columns)")

print()

# ------------------------------------------------------------------------------
# STEP 4: DATA INGESTION FROM NDJSON
# ------------------------------------------------------------------------------
print("=== STEP 4: STREAMING DATA FROM NDJSON INTO ENCRYPTED TABLES ===")

for span, meta_uuid in con.execute("SELECT span, meta_uuid FROM hubs ORDER BY span").fetchall():
    table_name = f"measurements_span{span}"
    
    columns = con.execute(f"DESCRIBE {table_name}").fetchall()
    
    insert_cols = []
    select_clauses = []
    
    for row in columns:
        col_name = row[0]
        insert_cols.append(col_name)
        
        if col_name == "timestamp":
            select_clauses.append("CAST(time_server_UTC AS TIMESTAMP)")
        elif col_name == "voltage":
            select_clauses.append("CAST(meta_power_battery_voltage AS FLOAT)")
        else:
            select_clauses.append(f"CAST({col_name} AS FLOAT)")
    
    insert_cols_sql = ", ".join(insert_cols)
    select_sql = ",\n        ".join(select_clauses)
    
    query = f"""
    INSERT INTO {table_name} ({insert_cols_sql})
    SELECT 
        {select_sql}
    FROM read_json_auto('{str(ndjson_path)}', ignore_errors=true)
    WHERE meta_uuid = {meta_uuid}
      AND time_server_UTC IS NOT NULL
    ON CONFLICT (timestamp) DO NOTHING;
    """
    
    try:
        expected_rows = con.execute(
            f"SELECT COUNT(*) FROM read_json_auto('{str(ndjson_path)}') "
            f"WHERE meta_uuid = {meta_uuid} AND time_server_UTC IS NOT NULL"
        ).fetchone()[0]

        con.execute(query)
        
        inserted_rows = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        duplicates_skipped = expected_rows - inserted_rows
        
        print(f"[{table_name}] Ingestion complete:")
        print(f"   Processed from source: {expected_rows}")
        print(f"   Successfully inserted: {inserted_rows}")
        if duplicates_skipped > 0:
            print(f"   Duplicates skipped:   {duplicates_skipped}")
        print()
            
    except Exception as e:
        print(f"[{table_name}] ERROR during ingestion: {e}\n")

# Close connection safely
con.close()
print("=== PIPELINE FINISHED SUCCESSFULLY: ENCRYPTED DATABASE BUILT ===")