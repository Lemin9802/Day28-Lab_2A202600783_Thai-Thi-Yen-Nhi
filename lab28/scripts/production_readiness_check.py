from __future__ import annotations

import os
import subprocess
from pathlib import Path

import redis
import requests

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
results: dict[str, str] = {}


def check(name: str, fn) -> None:
    try:
        fn()
        results[name] = "PASS"
        print(f"  [PASS] {name}")
    except Exception as exc:
        results[name] = f"FAIL: {exc}"
        print(f"  [FAIL] {name}: {exc}")


def assert_status(url: str, expected: tuple[int, ...] = (200,)) -> None:
    response = requests.get(url, timeout=5)
    assert response.status_code in expected, f"{url} returned {response.status_code}"


def check_api_fallback_path() -> None:
    response = requests.post(
        f"{API_GATEWAY_URL}/api/v1/chat",
        json={"query": "production readiness fallback test", "embedding": [0.0] * 384},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    assert "answer" in data
    assert data["latency_ms"] < 5000


def check_unauthorized() -> None:
    response = requests.get(f"{API_GATEWAY_URL}/admin", timeout=5)
    assert response.status_code in [401, 403, 404]


def check_qdrant_health() -> None:
    requests.get(f"{QDRANT_URL}/collections", timeout=5).raise_for_status()


def check_collection_exists() -> None:
    requests.get(f"{QDRANT_URL}/collections/documents", timeout=5).raise_for_status()


def check_redis_features() -> None:
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    assert client.ping()
    assert len(client.keys("feature:*")) > 0, "No feature:* keys found"


def check_kafka_topics() -> None:
    commands = [
        ["docker", "compose", "exec", "-T", "kafka", "kafka-topics", "--list", "--bootstrap-server", "kafka:29092"],
        ["docker", "exec", "lab28-kafka-1", "kafka-topics", "--list", "--bootstrap-server", "kafka:29092"],
    ]
    last_output = ""
    for command in commands:
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
        last_output = result.stdout + result.stderr
        if result.returncode == 0 and "data.raw" in result.stdout:
            return
    raise RuntimeError(f"data.raw topic not found. Last output: {last_output}")


def check_langsmith_configured() -> None:
    assert os.getenv("LANGCHAIN_API_KEY"), "LANGCHAIN_API_KEY is missing"
    assert os.getenv("LANGCHAIN_PROJECT", "lab28-platform")


def check_mlflow_initialized() -> None:
    assert (PROJECT_ROOT / "mlflow.db").exists() or (PROJECT_ROOT / "mlruns").exists(), "Run scripts/06_register_model_mlflow.py first"


print("\n=== RELIABILITY ===")
check("Health check endpoint", lambda: assert_status(f"{API_GATEWAY_URL}/health"))
check("Readiness endpoint", lambda: assert_status(f"{API_GATEWAY_URL}/ready"))
check("API Gateway docs", lambda: assert_status(f"{API_GATEWAY_URL}/docs"))
check("Fallback path responds", check_api_fallback_path)

print("\n=== OBSERVABILITY ===")
check("Prometheus up", lambda: assert_status(f"{PROMETHEUS_URL}/-/healthy"))
check("Grafana up", lambda: assert_status(f"{GRAFANA_URL}/api/health"))
check("Metrics endpoint exposed", lambda: assert_status(f"{API_GATEWAY_URL}/metrics"))
check("LangSmith env configured", check_langsmith_configured)

print("\n=== SECURITY ===")
check("Unauthorized request rejected", check_unauthorized)

print("\n=== VECTOR STORE ===")
check("Qdrant reachable", check_qdrant_health)
check("Qdrant collection exists", check_collection_exists)

print("\n=== FEATURE STORE ===")
check("Redis reachable and features exist", check_redis_features)

print("\n=== KAFKA ===")
check("Kafka topics exist", check_kafka_topics)

print("\n=== MODEL REGISTRY ===")
check("MLflow local registry initialized", check_mlflow_initialized)

passed = sum(1 for value in results.values() if value == "PASS")
total = len(results)
score = (passed / total) * 100
print(f"\n{'=' * 40}")
print(f"Production Readiness Score: {passed}/{total} = {score:.0f}%")
print(f"Target: >80% - Status: {'READY' if score >= 80 else 'NOT READY'}")
