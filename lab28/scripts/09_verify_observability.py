from __future__ import annotations

import os

import requests

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "lab28-platform")


def check_prometheus() -> None:
    metric_resp = requests.get(f"{API_GATEWAY_URL}/metrics", timeout=5)
    metric_resp.raise_for_status()
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": "up{job='api-gateway'}"},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["result"], "Prometheus has not scraped api-gateway yet"
    print("Integration 9 OK: Prometheus metrics flowing for API Gateway")


def check_langsmith() -> None:
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        raise RuntimeError("LANGCHAIN_API_KEY is missing")
    from langsmith import Client
    client = Client(api_key=api_key)
    runs = list(client.list_runs(project_name=LANGCHAIN_PROJECT, limit=1))
    assert len(runs) > 0, f"No LangSmith runs found in project {LANGCHAIN_PROJECT}"
    print(f"Integration 10 OK: LangSmith traces visible in project {LANGCHAIN_PROJECT}")


if __name__ == "__main__":
    check_prometheus()
    check_langsmith()
