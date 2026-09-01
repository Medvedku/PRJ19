import json
import tomllib
from pathlib import Path
from tqdm import tqdm


def flatten_dict(d, parent_key="", sep="_"):
    """Recursively flattens nested dictionaries."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            # Check for MongoDB extended JSON types like ObjectId or Date
            if "$oid" in v:
                items.append((new_key, v["$oid"]))
            elif "$date" in v:
                items.append((new_key, v["$date"]))
            else:
                items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def load_config(config_path="config.toml"):
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def main():
    print("[1/3] Reading configuration...")
    config = load_config()
    download_dir = Path(config["paths"]["download_dir"])

    input_file = download_dir / "PRJ-19.json"
    output_file = download_dir / "PRJ-19_flattened.ndjson"

    if not input_file.exists():
        raise FileNotFoundError(
            f"Input file not found at {input_file}. Run downloader.py first."
        )

    print(f"[2/3] Loading raw JSON from {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"[3/3] Flattening {len(records):,} records to NDJSON...")
    with open(output_file, "w", encoding="utf-8") as f_out, tqdm(
        total=len(records), desc="Flattening", unit="doc"
    ) as pbar:
        for doc in records:
            flat_doc = flatten_dict(doc)
            f_out.write(json.dumps(flat_doc, ensure_ascii=False) + "\n")
            pbar.update(1)

    print(f"\n✅ Success! Flattened NDJSON saved to {output_file.resolve()}")


if __name__ == "__main__":
    main()