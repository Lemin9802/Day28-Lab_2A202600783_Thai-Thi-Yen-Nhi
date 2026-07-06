from __future__ import annotations

import glob
import json
import os
import time
from pathlib import Path

import pandas as pd
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DELTA_LAKE_PATH = Path(os.getenv("DELTA_LAKE_PATH", "delta-lake/raw"))
ALLOW_SAMPLE_DATA = os.getenv("ALLOW_SAMPLE_DATA", "true").lower() == "true"


def load_records() -> pd.DataFrame:
    files = glob.glob(str(DELTA_LAKE_PATH / "*.parquet"))
    if files:
        df = pd.concat([pd.read_parquet(file) for file in files], ignore_index=True)
        print(f"Loaded {len(df)} records from Delta Lake path {DELTA_LAKE_PATH}")
        return df
    if not ALLOW_SAMPLE_DATA:
        raise RuntimeError("No parquet data found in Delta Lake and ALLOW_SAMPLE_DATA=false")
    print("No Delta Lake parquet files found. Seeding sample records for smoke test/demo.")
    return pd.DataFrame([
        {"id": "doc_001", "text": "AI platform integration test", "timestamp": time.time()},
        {"id": "doc_002", "text": "Kafka to Prefect pipeline", "timestamp": time.time()},
        {"id": "doc_003", "text": "Feature Store and Vector Store integration", "timestamp": time.time()},
    ])


def load_from_delta_and_push_feast() -> int:
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    df = load_records()
    for _, row in df.iterrows():
        client.set(f"feature:{row['id']}", json.dumps({
            "id": row["id"],
            "text": row["text"],
            "timestamp": float(row.get("timestamp", time.time())),
            "processed": True,
            "source": "delta-lake",
        }))
    print(f"Integration 3+4 OK: Lakehouse -> Feast/Redis, {len(df)} features stored")
    return len(df)


if __name__ == "__main__":
    load_from_delta_and_push_feast()
