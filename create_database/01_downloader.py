import json
import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv
import pymongo
from bson import json_util
from tqdm import tqdm


def load_config(config_path="config.toml"):
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def main():
    load_dotenv()

    # 1. Load configuration and setup output directory
    print("[1/4] Loading configuration...")
    config = load_config()
    download_dir = Path(config["paths"]["download_dir"])
    download_dir.mkdir(parents=True, exist_ok=True)

    output_file = download_dir / "PRJ-19.json"

    # 2. Connect to MongoDB
    print("[2/4] Connecting to MongoDB...")
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable is not set.")

    client = pymongo.MongoClient(mongo_uri)
    collection = client["prod"]["PRJ-19"]

    # 3. Get total document count for progress bar
    print("[3/4] Estimating collection size...")
    total_docs = collection.estimated_document_count()
    print(f"Found ~{total_docs:,} documents in 'prod.PRJ-19'.")

    # 4. Stream and write documents to JSON
    print(f"[4/4] Exporting collection to {output_file}...")
    documents = []

    cursor = collection.find()
    with tqdm(total=total_docs, desc="Downloading", unit="doc") as pbar:
        for doc in cursor:
            documents.append(doc)
            pbar.update(1)

    # Use bson.json_util to safely handle MongoDB types (ObjectIDs, ISODates)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(json_util.dumps(documents, indent=2))

    print(f"\n✅ Success! Saved to {output_file.resolve()}")


if __name__ == "__main__":
    main()