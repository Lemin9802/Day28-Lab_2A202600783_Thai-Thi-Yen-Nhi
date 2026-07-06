# smoke-tests/test_e2e.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")


def run_script(relative_path: str) -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / relative_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def qdrant_points_count() -> int:
    resp = requests.get("http://localhost:6333/collections/documents", timeout=5)
    if resp.status_code != 200:
        return 0
    return int(resp.json()["result"].get("points_count", 0))


class TestHappyPath:
    def test_full_inference_returns_200(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={"query": "What is platform engineering?", "embedding": [0.1] * 384},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 10
        assert data["latency_ms"] < 2000

    def test_health_check_passes(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestDataIngestion:
    def test_kafka_ingest_and_qdrant_store(self):
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        producer.send("data.raw", {"id": "smoke_001", "text": "smoke test document", "timestamp": time.time()})
        producer.flush()
        producer.close()

        run_script("scripts/05_embed_to_qdrant.py")
        count = qdrant_points_count()
        assert count > 0
        print(f"Vector store has {count} documents")


class TestObservability:
    def test_prometheus_scrapes_api_gateway(self):
        requests.get(f"{BASE_URL}/health", timeout=5).raise_for_status()
        time.sleep(2)
        resp = requests.get(
            "http://localhost:9090/api/v1/query",
            params={"query": "up{job='api-gateway'}"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()["data"]["result"]
        assert len(result) > 0
        assert result[0]["value"][1] == "1"

    def test_grafana_dashboard_accessible(self):
        resp = requests.get("http://localhost:3000/api/health", auth=("admin", "admin"), timeout=5)
        assert resp.status_code == 200


class TestFailurePath:
    def test_invalid_request_returns_422(self):
        resp = requests.post(f"{BASE_URL}/api/v1/chat", json={}, timeout=5)
        assert resp.status_code in [400, 422]

    def test_timeout_handled_gracefully(self):
        try:
            requests.post(
                f"{BASE_URL}/api/v1/chat",
                json={"query": "test", "embedding": [0.1] * 384},
                timeout=0.001,
            )
        except requests.exceptions.Timeout:
            pass

        health = requests.get(f"{BASE_URL}/health", timeout=5)
        assert health.status_code == 200


class TestFeatureStore:
    def test_feast_redis_has_features(self):
        import redis

        run_script("scripts/03_delta_to_feast.py")
        client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        keys = client.keys("feature:*")
        assert len(keys) > 0, "No features found in Feast/Redis store"
        print(f"Feature store has {len(keys)} feature entries")
