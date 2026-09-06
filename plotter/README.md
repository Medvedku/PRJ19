# Plotter Module (`plotter/`)

The `plotter` module provides automated data visualization utilities for sensor telemetry stored in the encrypted DuckDB database (`PRJ-19.duckdb`). It generates publication-quality, print-ready A4 landscape SVG charts for individual displacement sensors across structural spans.

---

## 🔑 Security & Credentials Note

> [!IMPORTANT]
> Execution of database-dependent plotting routines **will work only with `DB_PASS` (or `DP_PASS`)** configured in your `.env` file, as the underlying DuckDB database uses AES encryption. The codebase is complete, verified, and **ready to be reviewed**.

---

## 📁 Directory Structure & Components

```
plotter/
├── functions.py       # Core plotting, database resolution, and SVG generation library
├── plotting.ipynb     # Interactive Jupyter notebook for manual plot generation and testing
└── downloader.ipynb   # Utility notebook for automated DuckDB asset download
```

---

## 🛠️ Key Functionality (`functions.py`)

### 1. Database Connection & Remote Asset Management
* **`get_db_connection(config_path, db_name, read_only, auto_download)`**:
  - Automatically loads encryption credentials (`DB_PASS`) from `.env`.
  - Connects to and decrypts `PRJ-19.duckdb`.
  - If the database file is missing locally, it triggers `download_db_if_missing()` to automatically fetch the latest encrypted database asset from GitHub Release artifacts.
* **`load_all_tables(con)`**:
  - Reads all DuckDB tables (`hubs`, `sensors`, `measurements_span1..5`) into Pandas DataFrames for high-performance in-memory slicing.

### 2. Topology & Sensor Mapping
* **`find_span(sensor_id, df_hubs)`**: Maps a given sensor ID to its corresponding structural span.
* **`find_ref_sensor(sensor_id, df_hubs, df_sensors)`**: Identifies the reference sensor (type `Ref`) assigned to the same span for differential baseline comparison.

### 3. Visualization Engine (`plot_monthly_sensor_data`)
* **Data Processing**:
  - Filters measurements by month and year.
  - Applies sensor-specific tare offsets (`tare_pv0`, `tare_pv1`).
  - Scales displacement raw measurements (default multiplier: `25.0 mm/unit`).
* **Styling & Layout**:
  - Uses Seaborn (`whitegrid`) and Matplotlib configured for A4 Landscape dimensions (`24.69" x 8.27"` at 300 DPI).
  - Plots primary sensor displacement probes (`pv0`, `pv1`) alongside reference sensor curves (`Ref_pv0`, `Ref_pv1`).
  - Custom X-axis time formatting with Slovak day abbreviations (`Po`, `Ut`, `St`, `Št`, `Pi`, `So`, `Ne`) and day-of-week gridlines.
  - Exports crisp, vector-based SVG graphics (`save_a4_svg`) suitable for embedding into PDF documents.

---

## 🚀 Usage Example

```python
from plotter.functions import get_db_connection, load_all_tables, plot_monthly_sensor_data

# 1. Connect to encrypted DB
con = get_db_connection()
tables = load_all_tables(con)

# 2. Extract measurements and metadata
spans_data = {
    1: tables["measurements_span1"],
    2: tables["measurements_span2"],
    3: tables["measurements_span3"],
    4: tables["measurements_span4"],
    5: tables["measurements_span5"],
}

# 3. Generate monthly plot for Sensor #18 (March 2026)
plot_monthly_sensor_data(
    measurements_by_span=spans_data,
    df_sensors=tables["sensors"],
    df_hubs=tables["hubs"],
    sensor_id=18,
    year=2026,
    month=3,
    save_plot=True,
    output_path="charts/2026_03/01.svg",
    preview=False
)
```
