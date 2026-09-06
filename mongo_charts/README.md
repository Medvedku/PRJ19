# MongoDB Charts & Query Utilities (`mongo_charts/`)

The `mongo_charts` module contains MongoDB aggregation pipeline generators and query builders designed for real-time telemetry processing, live dashboards, and downsampling raw sensor streams.

---

## 🔑 Security & Credentials Note

> [!IMPORTANT]
> This module resolves sensor and hub metadata directly from the encrypted DuckDB instance (`PRJ-19.duckdb`), which **will work only with `DB_PASS` (or `DP_PASS`)** configured in `.env`. MongoDB dashboard queries can be extracted and executed against any MongoDB instance containing the raw `PRJ-19` collection. The code is finalized and **ready for review**.

---

## 📁 File Structure

```
mongo_charts/
└── functions_queries.py   # Aggregation pipeline generators and metadata lookup utilities
```

---

## 🛠️ Key Components (`functions_queries.py`)

### 1. Metadata Lookups
* Uses `get_db_connection()` and `load_all_tables()` to fetch sensor UUIDs, channel configurations, tare offsets, and reference sensor pairings directly from the DuckDB relational schema.
* `find_span()` and `find_ref_sensor()` resolve spatial relationships and reference sensors for differential calculations.

### 2. Optimized Resampling Aggregation Pipeline (`build_resampled_pipeline_for_sensor`)
Generates native MongoDB Aggregation Pipelines to perform server-side time-series resampling (downsampling) over historical time windows.

#### Pipeline Stages:
1. **`$match`**: Filters documents by sensor `meta.uuid`, date threshold (`days_back`), and field existence for target sensor and reference sensor channels.
2. **`$group` (`$dateTrunc`)**: Groups telemetry into uniform time bins (e.g., 1-hour or 6-hour intervals) and calculates server-side averages (`$avg`) for primary and reference probes (`pv0`, `pv1`).
3. **`$sort`**: Orders aggregated time buckets chronologically (`_id: 1`).
4. **`$project`**: Applies tare subtraction (`$subtract`) and scaling factors (`$multiply` by `25.0`) directly in MongoDB before returning data to the caller or chart widget.

---

## 💻 Code Example

```python
from mongo_charts.functions_queries import get_db_connection, load_all_tables, build_resampled_pipeline_for_sensor

# Connect to DuckDB metadata
con = get_db_connection()
tables = load_all_tables(con)
con.close()

# Generate a 31-day hourly resampled MongoDB aggregation pipeline for Sensor ID 18
pipeline = build_resampled_pipeline_for_sensor(
    sensor_id=18,
    df_sensors=tables["sensors"],
    df_hubs=tables["hubs"],
    days_back=31,
    multiplier=25.0,
    bin_size_hours=1
)

# You can now pass `pipeline` directly to pymongo:
# db["PRJ-19"].aggregate(pipeline)
```
