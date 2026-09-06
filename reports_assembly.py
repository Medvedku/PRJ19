import json
import os
import sys
import tomllib
from datetime import datetime
from pathlib import Path
import pandas as pd
import typst

from plotter.functions import (
    get_db_connection,
    load_all_tables,
    plot_monthly_sensor_data,
)

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


def resolve_config_path(raw_path: str, project_root: Path) -> Path:
    """Resolves raw path strings into absolute Path objects."""
    p = Path(raw_path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def verify_static_assets(
    config_path: Path,
    schema_path: Path,
    template_path: Path,
    logo_path: Path,
) -> None:
    """Pre-flight check to verify all required static files exist on disk."""
    print("=" * 60)
    print(" [DEBUG] RUNNING PRE-FLIGHT STATIC ASSET CHECK")
    print("=" * 60)

    assets = [
        ("Configuration File", config_path),
        ("Schema Mapping JSON", schema_path),
        ("Typst Template", template_path),
        ("Logo SVG", logo_path),
    ]

    missing_count = 0
    for label, path in assets:
        exists = path.is_file()
        status = "[OK]  " if exists else "[FAIL]"
        print(f"{status} {label:20s} -> {path}")
        if not exists:
            missing_count += 1

    print("-" * 60)
    try:
        con = get_db_connection()
        db_tables = load_all_tables(con)
        con.close()
        required_tables = ["sensors", "hubs", "measurements_span1"]
        for table in required_tables:
            if table in db_tables:
                print(f"[OK]   Database Table '{table}' loaded ({len(db_tables[table])} rows)")
            else:
                print(f"[FAIL] Database Table '{table}' missing")
                missing_count += 1
    except Exception as e:
        print(f"[FAIL] Database Connection Error: {e}")
        missing_count += 1

    print("=" * 60)
    if missing_count > 0:
        print(f"\nCRITICAL: {missing_count} static asset(s) or DB resources missing. Aborting run.\n")
        sys.exit(1)

    print(" ALL STATIC ASSETS & DB RESOURCES VERIFIED SUCCESSFULLY.")
    print("=" * 60 + "\n")


def build_reports() -> None:
    project_root = Path(".").resolve()
    config_path = project_root / "config.toml"

    if not config_path.is_file():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    paths_cfg = config.get("paths", {})
    schema_path = resolve_config_path(paths_cfg.get("schema_mapping", "config/schema_mapping.json"), project_root)
    charts_base_dir = resolve_config_path(paths_cfg.get("charts_dir", "charts"), project_root)
    report_base_dir = resolve_config_path(paths_cfg.get("report_dir", "report_build"), project_root)

    template_path = report_base_dir / "template.typ"
    logo_raw_path = paths_cfg.get("logo", "report_build/Metrotech01.svg")
    logo_path = resolve_config_path(logo_raw_path, project_root)

    verify_static_assets(
        config_path=config_path,
        schema_path=schema_path,
        template_path=template_path,
        logo_path=logo_path,
    )

    charts_base_dir.mkdir(parents=True, exist_ok=True)
    report_base_dir.mkdir(parents=True, exist_ok=True)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_mapping = json.load(f)

    print("[1/2] Connecting to database...")
    con = get_db_connection()
    db_tables = load_all_tables(con)
    df_sensors = db_tables["sensors"]
    df_hubs = db_tables["hubs"]

    spans_data = {
        1: db_tables["measurements_span1"],
        2: db_tables["measurements_span2"],
        3: db_tables["measurements_span3"],
        4: db_tables["measurements_span4"],
        5: db_tables["measurements_span5"],
    }
    con.close()

    months_to_process = [
        (2025, m) for m in range(10, 13)
    ] + [
        (2026, m) for m in range(1, 9)
    ]

    print(f"[2/2] Processing batch reports for {len(months_to_process)} months...\n")

    sorted_nodes = sorted(
        schema_mapping.items(), key=lambda item: item[1].get("Span", 0)
    )

    for year, month in months_to_process:
        month_str = f"{month:02d}"
        month_name_sk = SLOVAK_MONTHS[month]
        print(f"--- Processing: {month_name_sk} {year} ({month_str}/{year}) ---")

        month_charts_dir = charts_base_dir / f"{year}_{month_str}"
        month_report_dir = report_base_dir / f"{year}_{month_str}"
        month_charts_dir.mkdir(parents=True, exist_ok=True)
        month_report_dir.mkdir(parents=True, exist_ok=True)

        output_typ_path = month_report_dir / f"document_{month_str}_{year}.typ"
        output_pdf_path = report_base_dir / f"PRJ19_report_{month_str}_{year}.pdf"

        # Use absolute POSIX paths directly to avoid Typst path-resolution bugs
        abs_template_str = template_path.as_posix()
        abs_logo_str = logo_path.as_posix()

        typst_lines = [
            f'#import "{abs_template_str}": project, fullpage-image',
            "",
            "#show: project.with(",
            '  title: "M2717 - Slovenská Ľupča",',
            f'  subtitle: "{month_name_sk}, {year}",',
            '  author: "Ing. Jakub Rubint, PhD.",',
            f'  logo: "{abs_logo_str}"',
            ")",
            "",
        ]

        counter = 1
        charts_generated = 0

        for node_id, node_data in sorted_nodes:
            span = node_data.get("Span")
            sensors = node_data.get("sensors", {})

            sorted_sensors = sorted(
                sensors.items(), key=lambda item: int(item[1].get("position", 0))
            )

            for sensor_id_str, sensor_info in sorted_sensors:
                if sensor_info.get("type") == "DLeaf":
                    sensor_id = int(sensor_id_str)
                    position = sensor_info.get("position")

                    chart_filename = f"{counter:02d}.svg"
                    chart_abs_path = month_charts_dir / chart_filename

                    extra_kwargs = {}
                    if (year > 2026 or (year == 2026 and month >= 3)) and sensor_id == 18:
                        extra_kwargs["probes_sensor"] = ["pv1"]

                    plot_monthly_sensor_data(
                        measurements_by_span=spans_data,
                        df_sensors=df_sensors,
                        df_hubs=df_hubs,
                        width=17.0,
                        height=7.0,
                        sensor_id=sensor_id,
                        year=year,
                        month=month,
                        preview=False,
                        save_plot=True,
                        output_path=str(chart_abs_path),
                        **extra_kwargs,
                    )

                    # Absolute path for SVG charts
                    abs_chart_str = chart_abs_path.as_posix()

                    caption = fr"Pole {span}, Sensor {position}, (\#{sensor_id})"
                    typst_lines.append(
                        f'#fullpage-image("{abs_chart_str}", caption: [{caption}])'
                    )

                    counter += 1
                    charts_generated += 1

        print(f"  Generated {charts_generated} SVG charts.")

        generation_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        typst_lines.extend(
            [
                "  *Oznámenie o automatickom vygenerovaní reportu* \\",
                f"  Tento report bol automaticky vygenerovaný dňa {generation_timestamp}. ",
                '  Zdrojové kódy použitých algoritmov pre konverziu databázy z NoSQL na SQL, pre generovanie pipelines pre MongoDB dashboard, ako aj zdrojový kód pre samotné generovanie reportu sú dostupné v repozitári na #link("https://github.com/Medvedku/PRJ19")[github.com/Medvedku/PRJ19]. Prosím, pozorne si prečítajte dokumentáciu repozitára, prípadne zvážte použitie AI agenta pri reprodukcii. V prípade potreby ma môžete ohľadom kódu kontaktovať prostredníctvom údajov uvedených na mojom profile na GitHube.',
            ]
        )

        with open(output_typ_path, "w", encoding="utf-8") as f:
            f.write("\n".join(typst_lines))

        try:
            typst.compile(
                output_typ_path,
                output=output_pdf_path,
                root=Path("/"),
            )
            print(f"  Successfully compiled: {output_pdf_path.name}\n")
        except typst.TypstError as e:
            print(f"  Typst compilation failed for {month_str}/{year}:\n{e}\n")

    print("Assembly completed for all reports.")


if __name__ == "__main__":
    build_reports()