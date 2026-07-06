from __future__ import annotations

import json
import os
import time
from typing import Iterable

from kafka import KafkaProducer

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "data.raw")


def build_producer() -> KafkaProducer:
    last_error: Exception | None = None
    for attempt in range(1, 11):
        try:
            return KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                retries=5,
            )
        except Exception as exc:
            last_error = exc
            print(f"Kafka is starting, retry {attempt}/10...")
            time.sleep(3)
    raise RuntimeError(f"Could not create Kafka producer: {last_error}")


def ingest_data(records: Iterable[dict]) -> None:
    producer = build_producer()
    for record in records:
        producer.send(KAFKA_TOPIC, value=record)
        print(f"Sent to {KAFKA_TOPIC}: {record['id']}")
    producer.flush()
    producer.close()


if __name__ == "__main__":
    now = time.time()
    sample_data = [
        {"id": "doc_001", "text": "AI platform integration test", "timestamp": now},
        {"id": "doc_002", "text": "Kafka to Prefect pipeline", "timestamp": now},
        {"id": "doc_003", "text": "Qdrant vector search with vLLM serving", "timestamp": now},
    ]
    ingest_data(sample_data)
    print("Integration 1 OK: Data ingestion to Kafka")
