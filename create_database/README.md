# Database Extraction & Relational ETL (`create_database/`)

The `create_database` module contains the 3-step ETL (Extract, Transform, Load) data pipeline for PRJ-19. It extracts raw unstructured BSON documents from MongoDB, flattens nested telemetry objects, and builds an encrypted, relational DuckDB database (`PRJ-19.duckdb`).

---

## 🔑 Security & Credentials Note

> [!IMPORTANT]
> The database creation scripts **will work only with `DB_PASS` (or `DP_PASS`)** and `MONGODB_URI` set in `.env`. Step 3 generates an AES-encrypted DuckDB database file using `DB_PASS`. All scripts are tested and **ready to be reviewed**.

---

## 📁 Pipeline Overview

```
create_database/
├── 01_downloader.py   # Step 1: Export raw MongoDB collection to local JSON
├── 02_flatten.py      # Step 2: Recursively flatten nested JSON to NDJSON format
├── 03_build_db.py     # Step 3: Create schema & stream NDJSON into encrypted DuckDB tables
└── prj19/             # Intermediate storage / package directory
```

---

## ⚙️ Step-by-Step Execution Guide

### Step 1: Raw Document Extraction (`01_downloader.py`)
Connects to MongoDB Atlas using `MONGODB_URI` environment variable, queries the `prod.PRJ-19` collection, streams documents using `bson.json_util` to preserve MongoDB ObjectIDs and ISODates, and writes output to `data/PRJ-19.json`.

```bash
python create_database/01_downloader.py
```

### Step 2: Telemetry Flattening (`02_flatten.py`)
Reads `data/PRJ-19.json` and flattens nested key-value pairs recursively. Transforms BSON extended JSON types (`$oid`, `$date`) into flat string key representations suitable for relational ingestion. Exports `data/PRJ-19_flattened.ndjson`.

```bash
python create_database/02_flatten.py
```

### Step 3: Encrypted DuckDB Schema Build & Streaming Ingestion (`03_build_db.py`)
Initializes DuckDB with AES encryption enabled via `DB_PASS`.

1. **`hubs` Table**: Populates structural span mapping, hardware serial numbers (SN), and hub sensor ID arrays from `config/schema_mapping.json`.
2. **`sensors` Table**: Defines metadata for displacement sensors, including position, sensor type (`DLeaf`, `Ref`), probe arrays (`pv0`, `pv1`, `pv2`, `pv3`), and tare calibration values.
3. **`measurements_span1..5` Tables**: Dynamically generates relational measurement tables for each structural span, indexing time-series measurements with `timestamp TIMESTAMP PRIMARY KEY`.
4. **Streaming Ingestion**: Streams flattened NDJSON records into DuckDB tables using native `read_json_auto()`, skipping duplicate timestamp entries (`ON CONFLICT (timestamp) DO NOTHING`).

```bash
python create_database/03_build_db.py
```

---

## 📊 Relational Database Schema Overview

```mermaid
erdiagram
    HUBS {
        UBIGINT meta_uuid PK
        INT sn
        INT span
        INT[] sensors
    }
    SENSORS {
        INT sensor_id PK
        UBIGINT meta_uuid FK
        INT position
        VARCHAR type
        VARCHAR color
        VARCHAR[] probes
        DOUBLE tare_pv0
        DOUBLE tare_pv1
    }
    MEASUREMENTS_SPAN1 {
        TIMESTAMP timestamp PK
        FLOAT voltage
        FLOAT values_sensor_pv0
        FLOAT values_sensor_pv1
    }
    HUBS ||--|{ SENSORS : "contains"
    HUBS ||--|| MEASUREMENTS_SPAN1 : "stores span measurements"
```
