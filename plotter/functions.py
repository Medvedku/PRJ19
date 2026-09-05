import os
import tomllib
from pathlib import Path
import duckdb
from dotenv import load_dotenv
import urllib.request

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns

# Define project root relative to this file (plotter/ -> project root)
PROJECT_ROOT = Path(__file__).parent.parent

# A4 Landscape printable plot area constants (in inches)
A4_LANDSCAPE_WIDTH = 24.69
A4_LANDSCAPE_HEIGHT = 8.27

REPO = "Medvedku/PRJ19"

import json
import os
from pathlib import Path
import tomllib
import urllib.request
import duckdb
from dotenv import load_dotenv

REPO = "Medvedku/PRJ19"


def download_db_if_missing(
    db_path: Path, repo: str = REPO, user_agent: str = "PRJ19-Downloader"
) -> None:
    """Downloads the DuckDB database file from the latest repository release if it doesn't exist."""
    if db_path.exists():
        return

    print(f"Database not found at '{db_path.resolve()}'. Attempting download...")

    # Ensure target directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    releases_url = f"https://api.github.com/repos/{repo}/releases"
    req = urllib.request.Request(
        releases_url, headers={"User-Agent": user_agent}
    )

    with urllib.request.urlopen(req) as response:
        releases = json.loads(response.read().decode())

    if not releases:
        raise RuntimeError(f"No releases or pre-releases found for '{repo}'.")

    # Find the requested file across releases, starting from the newest
    download_url = None
    for release in releases:
        for asset in release.get("assets", []):
            if asset.get("name") == db_path.name:
                download_url = asset.get("browser_download_url")
                break
        if download_url:
            break

    if not download_url:
        raise FileNotFoundError(
            f"Asset '{db_path.name}' was not found in any releases for '{repo}'."
        )

    print(f"Downloading '{db_path.name}' from {download_url}...")
    urllib.request.urlretrieve(download_url, db_path)
    print(f"Successfully downloaded database to '{db_path.resolve()}'.")


def get_db_connection(
    config_path: str | Path = "config.toml",
    db_name: str = "PRJ-19.duckdb",
    read_only: bool = False,
    auto_download: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Establishes an encrypted DuckDB connection using environment variables and TOML config.

    Downloads the DB asset if missing and auto_download is True.
    """
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

    # Download if missing before attempting the connection
    if auto_download and not db_path.exists():
        download_db_if_missing(db_path)

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


# def setup_a4_landscape_plot(
#     width: float = A4_LANDSCAPE_WIDTH,
#     height: float = A4_LANDSCAPE_HEIGHT,
#     font_scale: float = 1.1,
# ) -> tuple[plt.Figure, plt.Axes]:
#     """Configures a Seaborn/Matplotlib figure sized specifically for full-page A4 landscape print layout."""
#     # Apply theme globally or outside plot generation
#     sns.set_theme(style="whitegrid", font_scale=font_scale)
    
#     # Explicitly instantiate figure with forward constraints
#     fig = plt.figure(figsize=(width, height), dpi=300)
#     ax = fig.add_subplot(1, 1, 1)
    
#     return fig, ax

def setup_a4_landscape_plot(
    width: float = A4_LANDSCAPE_WIDTH,
    height: float = A4_LANDSCAPE_HEIGHT,
    font_scale: float = 1.1,
) -> tuple[plt.Figure, plt.Axes]:
    """Configures a Seaborn/Matplotlib figure sized specifically for full-page A4 landscape print layout."""
    # Apply theme globally or outside plot generation
    sns.set_theme(style="whitegrid", font_scale=font_scale)
    
    # Explicitly instantiate figure with forward constraints
    fig = plt.figure(figsize=(width, height), dpi=300)
    ax = fig.add_subplot(1, 1, 1)
    
    return fig, ax



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

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns


def plot_monthly_sensor_data(
    measurements_by_span: dict[int, pd.DataFrame],
    df_sensors: pd.DataFrame,
    df_hubs: pd.DataFrame,
    sensor_id: int,
    year: int,
    month: int,
    scale_factor: float = 25.0,
    width: float = 10.5,
    height: float = 7.0,
    preview: bool = True,
    save_plot: bool = False,
    output_path: str | None = None,
) -> None:
    # 0. Automatically resolve span and select corresponding measurements DataFrame
    target_span = find_span(sensor_id, df_hubs)
    if target_span not in measurements_by_span:
        raise KeyError(
            f"Span {target_span} DataFrame not provided in measurements_by_span dictionary."
        )

    df_measurements = measurements_by_span[target_span]

    # 1. Get main sensor metadata
    sensor_row = df_sensors[df_sensors["sensor_id"] == sensor_id]
    if sensor_row.empty:
        raise ValueError(f"Sensor ID {sensor_id} not found in df_sensors.")

    sensor_info = sensor_row.iloc[0]
    position = sensor_info["position"]
    line_color = (
        sensor_info["color"]
        if pd.notna(sensor_info["color"]) and sensor_info["color"]
        else "#df77b4"
    )
    tare_pv0 = (
        sensor_info["tare_pv0"] if pd.notna(sensor_info["tare_pv0"]) else 0.0
    )
    tare_pv1 = (
        sensor_info["tare_pv1"] if pd.notna(sensor_info["tare_pv1"]) else 0.0
    )

    # Fetch reference sensor metadata
    ref_sensor_id = find_ref_sensor(sensor_id, df_hubs, df_sensors)
    ref_sensor_info = df_sensors[
        df_sensors["sensor_id"] == ref_sensor_id
    ].iloc[0]
    ref_tare_pv0 = (
        ref_sensor_info["tare_pv0"]
        if pd.notna(ref_sensor_info["tare_pv0"])
        else 0.0
    )
    ref_tare_pv1 = (
        ref_sensor_info["tare_pv1"]
        if pd.notna(ref_sensor_info["tare_pv1"])
        else 0.0
    )

    # 2. Set date boundaries for requested month
    start_date = pd.Timestamp(year=year, month=month, day=1)
    end_date = (
        start_date
        + pd.offsets.MonthEnd(1)
        + pd.Timedelta(hours=23, minutes=59, seconds=59)
    )

    df_filtered = df_measurements[
        (df_measurements["timestamp"] >= start_date)
        & (df_measurements["timestamp"] <= end_date)
    ].copy()

    if df_filtered.empty:
        print(
            f"No data available for Sensor {sensor_id} in {year}-{month:02d} (Span {target_span})."
        )
        return

    # 3. Subtract tare and scale for main and reference sensors
    df_filtered["pv0_scaled"] = (
        df_filtered[f"values_{sensor_id}_pv0"] - tare_pv0
    ) * scale_factor
    df_filtered["pv1_scaled"] = (
        df_filtered[f"values_{sensor_id}_pv1"] - tare_pv1
    ) * scale_factor

    df_filtered["ref_pv0_scaled"] = (
        df_filtered[f"values_{ref_sensor_id}_pv0"] - ref_tare_pv0
    ) * scale_factor
    df_filtered["ref_pv1_scaled"] = (
        df_filtered[f"values_{ref_sensor_id}_pv1"] - ref_tare_pv1
    ) * scale_factor

    # 4. Initialize Seaborn theme and figure directly
    sns.set_theme(style="whitegrid", font_scale=1.1)
    fig, ax = plt.subplots(figsize=(width, height), dpi=300)

    ax.grid(True, axis="y")
    ax.grid(False, axis="x")

    # 5. Draw plots for main sensor
    sns.lineplot(
        data=df_filtered,
        x="timestamp",
        y="pv0_scaled",
        ax=ax,
        color=line_color,
        label=f"S_{sensor_id}_pv0",
        zorder=3,
    )
    sns.lineplot(
        data=df_filtered,
        x="timestamp",
        y="pv1_scaled",
        ax=ax,
        color=line_color,
        alpha=0.7,
        linestyle="-",
        label=f"S_{sensor_id}_pv1",
        zorder=3,
    )

    # Draw plots for reference sensor
    sns.lineplot(
        data=df_filtered,
        x="timestamp",
        y="ref_pv0_scaled",
        ax=ax,
        color="#000000",
        alpha=0.9,
        label=f"Ref_{ref_sensor_id}_pv0",
        zorder=3,
    )
    sns.lineplot(
        data=df_filtered,
        x="timestamp",
        y="ref_pv1_scaled",
        ax=ax,
        color="#000000",
        alpha=0.7,
        linestyle="-",
        label=f"Ref_{ref_sensor_id}_pv1",
        zorder=3,
    )

    # Configure 2-column legend inside the plot window
    legend_fontsize = 9
    ax.legend(
        ncols=2,
        fontsize=legend_fontsize,
        loc="upper right",
        frameon=True,
        framealpha=0.8,
    )

    # 6. Set hard plot limits
    ax.set_xlim(start_date, end_date)
    ax.set_ylim(-0.25, 0.25)

    # 7. Set daily ticks and custom label formatter with Slovak day names
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))

    SLOVAK_DAYS = ["Po", "Ut", "St", "Št", "Pi", "So", "Ne"]

    def custom_date_formatter(x, pos=None):
        dt = mdates.num2date(x)
        day_num = dt.strftime("%d")
        if dt.weekday() == 6:  # Sunday
            return f"{day_num} {SLOVAK_DAYS[6]}"
        return day_num

    ax.xaxis.set_major_formatter(ticker.FuncFormatter(custom_date_formatter))

    # 8. Custom vertical gridlines with day-of-week alpha
    BASE_COLOR = "#000000"
    ALPHA_DAYS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.80]
    ALPHA_DAYS = [a * 0.5 for a in ALPHA_DAYS]

    all_days = pd.date_range(
        start=start_date.floor("D"),
        end=end_date.floor("D"),
        freq="D",
    )

    for day in all_days:
        day_alpha = ALPHA_DAYS[day.weekday()]
        ax.axvline(
            x=day,
            color=BASE_COLOR,
            linestyle="-",
            linewidth=0.8,
            alpha=day_alpha,
            zorder=1,
        )

    # 9. Titles and formatting
    SLOVAK_MONTHS = {
        1: "Január",
        2: "Február",
        3: "Marec",
        4: "Apríl",
        5: "Máj",
        6: "Jún",
        7: "Júl",
        8: "August",
        9: "September",
        10: "Október",
        11: "November",
        12: "December",
    }
    month_name_sk = SLOVAK_MONTHS[month]

    ax.set_title(
        f"Pole {target_span}, Senzor {position} (#{sensor_id})\n{month_name_sk} {year}",
        fontsize=15,
        pad=14,
    )
    ax.set_xlabel("")
    ax.set_ylabel("Vzdialenosť [mm]", fontsize=12)
    plt.xticks(rotation=45, ha="right", fontsize=10)

    # 10. Handle saving and displaying inside Jupyter Notebook
    if save_plot:
        # Resolves custom output_path if provided; otherwise falls back to default naming
        filename = (
            output_path
            if output_path is not None
            else f"sensor_{sensor_id}_{year}_{month:02d}.svg"
        )
        save_a4_svg(fig, filename)

    if preview:
        plt.show()
    else:
        plt.close(fig)


def save_a4_svg(fig: plt.Figure, filename: str) -> None:
    """Saves the figure as a high-precision print-ready SVG vector file."""
    fig.savefig(
        filename,
        format="svg",
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.close(fig)