#!/usr/bin/env python3
"""
copy-collections/main.py

Copy MongoDB/CosmosDB collections matching a regex pattern from an origin
database to a destination database, using batched upserts.

Connection strings and database names are read from a .env file located
in the same directory as this script.

Usage:
    python main.py --pattern "mydblocal-.*"

Requires:
    pip install pymongo python-dotenv
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

SCRIPT_DIR = Path(__file__).parent.resolve()
TMP_DIR = SCRIPT_DIR / "tmp"
STATE_FILE = TMP_DIR / "state.json"
BATCH_SIZE = 1000


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    env_path = SCRIPT_DIR / ".env"
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_path)

    required = ["ORIGIN_URI", "ORIGIN_DB", "DEST_URI", "DEST_DB"]
    config = {}
    missing = []

    for key in required:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        else:
            config[key] = value

    if missing:
        print(f"Error: missing required variables in .env: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    return config


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def batch_key(collection: str, batch_index: int) -> str:
    return f"{collection}::batch_{batch_index:06d}"


def batch_tmp_path(collection: str, batch_index: int) -> Path:
    col_dir = TMP_DIR / collection
    col_dir.mkdir(parents=True, exist_ok=True)
    return col_dir / f"batch_{batch_index:06d}.jsonl"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def list_matching_collections(db, pattern: str) -> list[str]:
    regex = re.compile(pattern)
    return sorted(name for name in db.list_collection_names() if regex.fullmatch(name))


def write_batch_checkpoint(collection: str, batch_index: int, docs: list) -> Path:
    path = batch_tmp_path(collection, batch_index)
    with open(path, "w") as f:
        for doc in docs:
            f.write(json_util.dumps(doc) + "\n")
    return path


def upsert_batch(dest_col, docs: list) -> tuple[int, int]:
    """Returns (upserted, modified)."""
    operations = [
        UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {k: v for k, v in doc.items() if k != "_id"}},
            upsert=True,
        )
        for doc in docs
    ]
    try:
        result = dest_col.bulk_write(operations, ordered=False)
        return result.upserted_count, result.modified_count
    except BulkWriteError as e:
        details = e.details
        return details.get("nUpserted", 0), details.get("nModified", 0)


def copy_indexes(origin_col, dest_col):
    created = 0
    for index in origin_col.list_indexes():
        if index["name"] == "_id_":
            continue
        keys = list(index["key"].items())
        options = {k: v for k, v in index.items() if k not in ("key", "ns", "v", "name")}
        dest_col.create_index(keys, **options)
        created += 1
    if created:
        print(f"  Indexes created: {created}")


def copy_collection(origin_col, dest_col, col_name: str, state: dict, resume: bool, max_docs: int = 0):
    print(f"\n  Collection: {col_name}")

    total_docs = origin_col.estimated_document_count()
    print(f"  Estimated documents: {total_docs:,}")

    limit = max_docs if max_docs > 0 else 0
    cursor = origin_col.find({}, batch_size=BATCH_SIZE).limit(limit)
    batch_index = 0
    total_upserted = 0
    total_modified = 0
    total_skipped = 0
    buffer = []

    for doc in cursor:
        buffer.append(doc)

        if len(buffer) == BATCH_SIZE:
            key = batch_key(col_name, batch_index)

            if resume and state.get(key) == "done":
                print(f"    Batch {batch_index:06d}: skipped (already done)")
                total_skipped += BATCH_SIZE
                buffer = []
                batch_index += 1
                continue

            write_batch_checkpoint(col_name, batch_index, buffer)
            ups, mod = upsert_batch(dest_col, buffer)
            total_upserted += ups
            total_modified += mod

            state[key] = "done"
            save_state(state)

            print(f"    Batch {batch_index:06d}: {len(buffer)} docs — "
                  f"upserted={ups}, modified={mod}")

            buffer = []
            batch_index += 1

    # Last partial batch
    if buffer:
        key = batch_key(col_name, batch_index)

        if resume and state.get(key) == "done":
            total_skipped += len(buffer)
            print(f"    Batch {batch_index:06d}: skipped (already done)")
        else:
            write_batch_checkpoint(col_name, batch_index, buffer)
            ups, mod = upsert_batch(dest_col, buffer)
            total_upserted += ups
            total_modified += mod
            state[key] = "done"
            save_state(state)
            print(f"    Batch {batch_index:06d}: {len(buffer)} docs — "
                  f"upserted={ups}, modified={mod}")

    copy_indexes(origin_col, dest_col)

    state[f"{col_name}::complete"] = datetime.utcnow().isoformat()
    save_state(state)

    print(f"  Done — upserted={total_upserted}, modified={total_modified}, "
          f"skipped={total_skipped}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def prompt_cleanup():
    print()
    answer = input("Do you want to clean up the ./tmp directory? [y/N]: ").strip().lower()
    if answer == "y":
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        print("  ./tmp removed.")
    else:
        print("  ./tmp kept.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy MongoDB/CosmosDB collections matching a regex pattern."
    )
    parser.add_argument(
        "--pattern",
        required=True,
        help="Regex to match collection names (e.g. 'mydblocal-.*')",
    )
    parser.add_argument(
        "--max-docs-per-col",
        type=int,
        default=0,
        help="Maximum number of documents to copy per collection (0 = no limit)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    # --- Check for existing state / resume ---
    resume = False
    state = load_state()

    if state:
        print("Existing progress found in ./tmp/state.json.")
        answer = input("Resume from last checkpoint? [y/N]: ").strip().lower()
        resume = answer == "y"
        if not resume:
            print("Starting fresh — clearing previous state.")
            shutil.rmtree(TMP_DIR, ignore_errors=True)
            state = {}

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # --- Connect ---
    print("\nConnecting to origin...")
    origin_client = MongoClient(config["ORIGIN_URI"])
    origin_db = origin_client[config["ORIGIN_DB"]]

    print("Connecting to destination...")
    dest_client = MongoClient(config["DEST_URI"])
    dest_db = dest_client[config["DEST_DB"]]

    # --- Discover collections ---
    collections = list_matching_collections(origin_db, args.pattern)

    if not collections:
        print(f"\nNo collections found matching pattern '{args.pattern}' "
              f"in '{config['ORIGIN_DB']}'.")
        sys.exit(0)

    print(f"\nCollections to copy ({len(collections)}):")
    for name in collections:
        status = "complete" if state.get(f"{name}::complete") else "pending"
        print(f"  {name}  [{status}]")

    print()

    # --- Copy ---
    start = datetime.utcnow()

    for col_name in collections:
        if resume and state.get(f"{col_name}::complete"):
            print(f"\n  Collection: {col_name}  [already complete, skipping]")
            continue

        copy_collection(
            origin_col=origin_db[col_name],
            dest_col=dest_db[col_name],
            col_name=col_name,
            state=state,
            resume=resume,
            max_docs=args.max_docs_per_col,
        )

    elapsed = (datetime.utcnow() - start).total_seconds()
    print(f"\nAll done in {elapsed:.1f}s.")

    origin_client.close()
    dest_client.close()

    prompt_cleanup()


if __name__ == "__main__":
    main()
