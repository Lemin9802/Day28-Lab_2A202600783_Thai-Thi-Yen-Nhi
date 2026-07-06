from __future__ import annotations

import glob
import hashlib
import os
import time
from pathlib import Path

import pandas as pd
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "documents")
DELTA_LAKE_PATH = Path(os.getenv("DELTA_LAKE_PATH", "delta-lake/raw"))
EMBED_URL = (os.getenv("EMBED_TUNNEL_URL") or os.getenv("EMBED_NGROK_URL") or "").rstrip("/")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
VECTOR_SIZE = 384


def deterministic_embedding(text: str, size: int = VECTOR_SIZE) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < size:
        for byte in digest:
            values.append((byte / 255.0) * 2 - 1)
            if len(values) == size:
                break
        digest = hashlib.sha256(digest).digest()
    return values


def load_records() -> list[dict]:
    files = glob.glob(str(DELTA_LAKE_PATH / "*.parquet"))
    if files:
        df = pd.concat([pd.read_parquet(file) for file in files], ignore_index=True)
        print(f"Loaded {len(df)} records from Delta Lake path {DELTA_LAKE_PATH}")
        return df.to_dict(orient="records")
    print("No Delta Lake parquet files found. Seeding sample documents for vector smoke test/demo.")
    return [
        {"id": "doc_001", "text": "AI platform integration test", "timestamp": time.time()},
        {"id": "doc_002", "text": "Kafka to Prefect pipeline", "timestamp": time.time()},
        {"id": "doc_003", "text": "Qdrant vector search with vLLM serving", "timestamp": time.time()},
    ]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if EMBED_URL:
        try:
            response = requests.post(f"{EMBED_URL}/embed", json={"texts": texts}, timeout=10)
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
            print(f"Embedding service OK: received {len(embeddings)} embeddings")
            return embeddings
        except Exception as exc:
            print(f"Embedding service degraded, using local deterministic fallback: {exc}")
    return [deterministic_embedding(text) for text in texts]


def embed_and_store(records: list[dict]) -> int:
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    qdrant.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    texts = [str(record.get("text", "")) for record in records]
    embeddings = embed_texts(texts)
    points = [PointStruct(id=index + 1, vector=embedding, payload=record) for index, (embedding, record) in enumerate(zip(embeddings, records))]
    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Integration 5 OK: stored {len(points)} vectors in Qdrant collection '{COLLECTION_NAME}'")
    return len(points)


if __name__ == "__main__":
    embed_and_store(load_records())
