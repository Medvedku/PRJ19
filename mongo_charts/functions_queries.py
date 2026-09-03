import pandas as pd
import os
import tomllib
from pathlib import Path
import duckdb
from dotenv import load_dotenv

# Define project root relative to this file (plotter/ -> project root)
PROJECT_ROOT = Path(__file__).parent.parent

def get_db_connection(
    config_path: str | Path = "config.toml",
    db_name: str = "PRJ-19.duckdb",
    read_only: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Establishes an encrypted DuckDB connection using environment variables and TOML config."""
    # Resolve .env relative to project root
    load_dotenv(PROJECT_ROOT / ".env")
    db_pass = os.getenv("DB_PASS")

    if not db_pass:
        raise ValueError("DB_PASS environment variable not found in .env")

    # Resolve config.toml relative to project root if a relative path is passed
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = PROJECT_ROOT / config_file

    if not config_file.exists():
        raise FileNotFoundError(
            f"Config file not found at: {config_file.resolve()}"
        )

    with open(config_file, "rb") as f:
        config = tomllib.load(f)

    # Resolve db_dir relative to project root if it's a relative path
    db_dir = Path(config["paths"]["db_dir"])
    if not db_dir.is_absolute():
        db_dir = PROJECT_ROOT / db_dir

    db_path = db_dir / db_name

    if not db_path.exists():
        raise FileNotFoundError(
            f"Database file not found at: {db_path.resolve()}"
        )

    con = duckdb.connect(read_only=read_only)
    con.execute(f"ATTACH '{db_path}' AS db (ENCRYPTION_KEY '{db_pass}');")
    con.execute("USE db;")

    return con


def load_all_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """Loads all tables from the connected DuckDB instance into a dictionary of DataFrames."""
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    return {
        table: con.execute(f"SELECT * FROM {table}").df() for table in tables
    }


def find_span(sensor_id: int, df_hubs: pd.DataFrame) -> int:
    """Finds the span number for a given sensor_id using df_hubs."""
    span_row = df_hubs[
        df_hubs["sensors"].apply(lambda sensors: sensor_id in sensors)
    ]
    if span_row.empty:
        raise ValueError(f"Sensor ID {sensor_id} not found in any hub/span.")
    return int(span_row.iloc[0]["span"])


def find_ref_sensor(
    sensor_id: int, df_hubs: pd.DataFrame, df_sensors: pd.DataFrame
) -> int:
    """Finds the reference sensor (type 'Ref') for the span containing the given sensor_id."""
    span_row = df_hubs[
        df_hubs["sensors"].apply(lambda sensors: sensor_id in sensors)
    ]
    if span_row.empty:
        raise ValueError(f"Sensor ID {sensor_id} not found in any hub/span.")

    span_sensors = span_row.iloc[0]["sensors"]
    ref_sensor_row = df_sensors[
        (df_sensors["sensor_id"].isin(span_sensors))
        & (df_sensors["type"] == "Ref")
    ]

    if ref_sensor_row.empty:
        raise ValueError(
            f"No reference sensor (type 'Ref') found for span containing sensor {sensor_id}."
        )

    return int(ref_sensor_row.iloc[0]["sensor_id"])


def build_resampled_pipeline_for_sensor(
    sensor_id: int,
    df_sensors: pd.DataFrame,
    df_hubs: pd.DataFrame,
    days_back: int = 31,
    multiplier: float = 25.0,
    bin_size_hours: int = 1,  # e.g., 1 for hourly bins, 6 for 6-hour bins
) -> list:
    """Builds an optimized MongoDB aggregation pipeline that resamples (downsamples)

    telemetry into fixed time bins (e.g., 1-hour or 6-hour averages).
    """
    # 1. Look up primary sensor metadata
    sensor_row = df_sensors[df_sensors["sensor_id"] == sensor_id]
    if sensor_row.empty:
        raise ValueError(f"Sensor ID {sensor_id} not found in df_sensors.")
    sensor_info = sensor_row.iloc[0]

    uuid = int(sensor_info["meta_uuid"])
    s_type = str(sensor_info["type"])
    s_id_str = str(sensor_id)
    s_pv0_offset = float(sensor_info["tare_pv0"])
    s_pv1_offset = float(sensor_info["tare_pv1"])

    # 2. Look up reference sensor using df_hubs
    span_row = df_hubs[df_hubs["sensors"].apply(lambda s: sensor_id in s)]
    if span_row.empty:
        raise ValueError(f"Sensor ID {sensor_id} not found in any hub/span.")

    span_sensors = span_row.iloc[0]["sensors"]
    ref_sensor_row = df_sensors[
        (df_sensors["sensor_id"].isin(span_sensors))
        & (df_sensors["type"] == "Ref")
    ]
    if ref_sensor_row.empty:
        raise ValueError(
            f"No reference sensor ('Ref') found for span containing sensor {sensor_id}."
        )

    ref_row = ref_sensor_row.iloc[0]
    ref_id = int(ref_row["sensor_id"])
    r_type = str(ref_row["type"])
    r_id_str = str(ref_id)
    r_pv0_offset = float(ref_row["tare_pv0"])
    r_pv1_offset = float(ref_row["tare_pv1"])

    # Define dynamic field names for final projection
    s_pv0_out = f"S_{s_id_str}_pv0"
    s_pv1_out = f"S_{s_id_str}_pv1"
    r_pv0_out = f"R_{r_id_str}_pv0"
    r_pv1_out = f"R_{r_id_str}_pv1"

    # # 3. Construct and return MongoDB Aggregation Pipeline
    # return [
    #     {
    #         "$match": {
    #             "meta.uuid": uuid,
    #             "$expr": {
    #                 "$gte": [
    #                     "$time.server.UTC",
    #                     {
    #                         "$dateToString": {
    #                             "date": {
    #                                 "$dateSubtract": {
    #                                     "startDate": "$$NOW",
    #                                     "unit": "day",
    #                                     "amount": days_back,
    #                                 }
    #                             },
    #                             "format": "%Y-%m-%dT%H:%M:%S",
    #                         }
    #                     },
    #                 ]
    #             },
    #             "$or": [
    #                 {f"values.{s_id_str}": {"$exists": True}},
    #                 {f"values.{r_id_str}": {"$exists": True}},
    #             ],
    #         }
    #     },
    #     {
    #         "$project": {
    #             "_id": 0,
    #             "time_date": {
    #                 "$dateFromString": {"dateString": "$time.server.UTC"}
    #             },
    #             "v_sensor_pv0": f"$values.{s_id_str}.pv0",
    #             "v_sensor_pv1": f"$values.{s_id_str}.pv1",
    #             "v_ref_pv0": f"$values.{r_id_str}.pv0",
    #             "v_ref_pv1": f"$values.{r_id_str}.pv1",
    #         }
    #     },
    #     {
    #         "$setWindowFields": {
    #             "sortBy": {"time_date": 1},
    #             "output": {
    #                 "v_sensor_pv0": {
    #                     "$avg": "$v_sensor_pv0",
    #                     "window": {
    #                         "range": [-window_hours, "current"],
    #                         "unit": "hour",
    #                     },
    #                 },
    #                 "v_sensor_pv1": {
    #                     "$avg": "$v_sensor_pv1",
    #                     "window": {
    #                         "range": [-window_hours, "current"],
    #                         "unit": "hour",
    #                     },
    #                 },
    #                 "v_ref_pv0": {
    #                     "$avg": "$v_ref_pv0",
    #                     "window": {
    #                         "range": [-window_hours, "current"],
    #                         "unit": "hour",
    #                     },
    #                 },
    #                 "v_ref_pv1": {
    #                     "$avg": "$v_ref_pv1",
    #                     "window": {
    #                         "range": [-window_hours, "current"],
    #                         "unit": "hour",
    #                     },
    #                 },
    #             },
    #         }
    #     },
    #     {
    #         "$project": {
    #             "_id": 0,
    #             "time": "$time_date",
    #             s_pv0_out: {
    #                 "$multiply": [
    #                     {"$subtract": ["$v_sensor_pv0", s_pv0_offset]},
    #                     multiplier,
    #                 ]
    #             },
    #             s_pv1_out: {
    #                 "$multiply": [
    #                     {"$subtract": ["$v_sensor_pv1", s_pv1_offset]},
    #                     multiplier,
    #                 ]
    #             },
    #             r_pv0_out: {
    #                 "$multiply": [
    #                     {"$subtract": ["$v_ref_pv0", r_pv0_offset]},
    #                     multiplier,
    #                 ]
    #             },
    #             r_pv1_out: {
    #                 "$multiply": [
    #                     {"$subtract": ["$v_ref_pv1", r_pv1_offset]},
    #                     multiplier,
    #                 ]
    #             },
    #         }
    #     },
    # ]

    return [
        # Stage 1: Fast filter on UUID, date cutoff, and sensor existence
        {
            "$match": {
                "meta.uuid": uuid,
                "$expr": {
                    "$gte": [
                        "$time.server.UTC",
                        {
                            "$dateToString": {
                                "date": {
                                    "$dateSubtract": {
                                        "startDate": "$$NOW",
                                        "unit": "day",
                                        "amount": days_back,
                                    }
                                },
                                "format": "%Y-%m-%dT%H:%M:%S",
                            }
                        },
                    ]
                },
                "$or": [
                    {f"values.{s_id_str}": {"$exists": True}},
                    {f"values.{r_id_str}": {"$exists": True}},
                ],
            }
        },
        # Stage 2: Group by truncated time bin and average raw values
        {
            "$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": {
                            "$dateFromString": {
                                "dateString": "$time.server.UTC"
                            }
                        },
                        "unit": "hour",
                        "binSize": bin_size_hours,
                    }
                },
                "v_sensor_pv0": {"$avg": f"$values.{s_id_str}.pv0"},
                "v_sensor_pv1": {"$avg": f"$values.{s_id_str}.pv1"},
                "v_ref_pv0": {"$avg": f"$values.{r_id_str}.pv0"},
                "v_ref_pv1": {"$avg": f"$values.{r_id_str}.pv1"},
            }
        },
        # Stage 3: Sort by time ascending (grouping breaks order)
        {"$sort": {"_id": 1}},
        # Stage 4: Apply offsets and multipliers once per bin
        {
            "$project": {
                "_id": 0,
                "time": "$_id",
                s_pv0_out: {
                    "$multiply": [
                        {"$subtract": ["$v_sensor_pv0", s_pv0_offset]},
                        multiplier,
                    ]
                },
                s_pv1_out: {
                    "$multiply": [
                        {"$subtract": ["$v_sensor_pv1", s_pv1_offset]},
                        multiplier,
                    ]
                },
                r_pv0_out: {
                    "$multiply": [
                        {"$subtract": ["$v_ref_pv0", r_pv0_offset]},
                        multiplier,
                    ]
                },
                r_pv1_out: {
                    "$multiply": [
                        {"$subtract": ["$v_ref_pv1", r_pv1_offset]},
                        multiplier,
                    ]
                },
            }
        },
    ]