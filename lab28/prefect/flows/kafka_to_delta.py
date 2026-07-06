from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from kafka import KafkaConsumer

try:
    from prefect import flow, task
except Exception:
    def task(_func: Callable | None = None, *_args: Any, **_kwargs: Any):
        def decorator(func: Callable):
            return func
        if callable(_func):
            return _func
        return decorator

    def flow(_func: Callable | None = None, *_args: Any, **_kwargs: Any):
        def decorator(func: Callable):
            return func
        if callable(_func):
            return _func
        return decorator

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "data.raw")
DELTA_LAKE_PATH = Path(os.getenv("DELTA_LAKE_PATH", "/opt/delta-lake/raw"))


@task(retries=3, retry_delay_seconds=5)
def consume_and_process() -> list[dict]:
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=f"lab28-prefect-{int(time.time())}",
        consumer_timeout_ms=5000,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    records = [msg.value for msg in consumer]
    print(f"Consumed {len(records)} records from Kafka topic {KAFKA_TOPIC}")
    return records


@task
def save_to_delta(records: list[dict]) -> str | None:
    if not records:
        print("No records to save")
        return None
    DELTA_LAKE_PATH.mkdir(parents=True, exist_ok=True)
    output_path = DELTA_LAKE_PATH / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    pd.DataFrame(records).to_parquet(output_path, index=False)
    print(f"Saved {len(records)} records to Delta Lake path {output_path}")
    return str(output_path)


@flow(name="Kafka to Delta Pipeline")
def kafka_to_delta_flow() -> str | None:
    return save_to_delta(consume_and_process())


if __name__ == "__main__":
    if os.getenv("PREFECT_MODE", "run") == "serve" and hasattr(kafka_to_delta_flow, "serve"):
        kafka_to_delta_flow.serve(name="kafka-to-delta", interval=300)
    else:
        kafka_to_delta_flow()
