# Day 16 to Day 27 Integration Map for Lab 28

Lab 28 is the final integration sprint. The goal is not only to run a local Docker stack, but to show how the work from Day 16 to Day 27 is consolidated into one AI platform demo.

This document maps each prior lab to the Lab 28 runtime, evidence, and demo story.

---

## Source repositories

| Day | Repository |
|---:|---|
| 16 | https://github.com/Lemin9802/2A202600783_Thai-Thi-Yen-Nhi_Day16_Lab |
| 17 | https://github.com/Lemin9802/Day17_2A202600783_Thai-Thi-Yen-Nhi |
| 18 | https://github.com/Lemin9802/2A202600783_Thai-Thi-Yen-Nhi_Day18-Lab |
| 19 | https://github.com/Lemin9802/Day19_2A202600783_Thai-Thi-Yen-Nhi |
| 20 | https://github.com/Lemin9802/Day20_2A202600783_Thai-Thi-Yen-Nhi |
| 21 | https://github.com/Lemin9802/Day21_Mlops-Lab_2A202600783_Thai-Thi-Yen-Nhi |
| 22 | https://github.com/Lemin9802/Day22-Lab_2A202600783_Thai-Thi-Yen-Nhi |
| 23 | https://github.com/Lemin9802/Day23-Lab_2A202600783_Thai-Thi-Yen-Nhi |
| 24 | https://github.com/Lemin9802/Day24-Lab_2A202600783_Thai-Thi-Yen-Nhi |
| 25 | https://github.com/Lemin9802/Day25-Lab_2A202600783_Thai-Thi-Yen-Nhi |
| 26 | https://github.com/Lemin9802/Day26-Lab_2A202600783_Thai-Thi-Yen-Nhi |
| 27 | https://github.com/Lemin9802/Day27-Lab_2A202600783_Thai-Thi-Yen-Nhi |

---

## Cross-day integration summary

| Prior lab | Original capability | How Lab 28 uses it |
|---|---|---|
| Day 16 | Cloud infrastructure, Terraform IaC, CPU fallback deployment, benchmark evidence | Provides the infrastructure and fallback design rationale. Lab 28 keeps graceful degradation and uses local Docker + Kaggle GPU as the hybrid runtime. |
| Day 17 | Medallion-style data pipeline, validation/quarantine, Silver/Gold aggregation, streaming idempotency, RAG ingestion | Lab 28 implements the event-driven ingestion path: `scripts/01_ingest_to_kafka.py` -> Kafka topic `data.raw` -> pipeline flow. |
| Day 18 | Delta Lakehouse, Bronze/Silver/Gold, schema evolution, optimization, time travel | Lab 28 writes processed Kafka records to local lakehouse parquet under `delta-lake/raw`, representing the Delta/Lakehouse layer. |
| Day 19 | Qdrant vector store, hybrid semantic search, Feast feature store, Redis online store | Lab 28 uses Qdrant collection `documents` for vector retrieval and Redis `feature:*` keys as the online feature store. |
| Day 20 | Model serving, OpenAI-compatible endpoint, latency/load benchmarks, Milestone 1 end-to-end demo | Lab 28 API Gateway calls an OpenAI-compatible Kaggle vLLM endpoint at `/v1/chat/completions` when `VLLM_TUNNEL_URL` is configured. |
| Day 21 | MLOps CI/CD, DVC, MLflow/DagsHub tracking, model training/evaluation/deployment | Lab 28 includes `scripts/06_register_model_mlflow.py` to initialize MLflow tracking and register the fallback serving model metadata. |
| Day 22 | LangSmith tracing, prompt versioning, RAGAS evaluation, guardrails validators | Lab 28 wraps the chat pipeline with LangSmith tracing via `lab28_chat_pipeline` and validates traces with `scripts/09_verify_observability.py`. |
| Day 23 | Observability stack: Prometheus, Grafana, traces, logs, drift, cross-day integration | Lab 28 exposes `/metrics`, Prometheus scrapes API Gateway, Grafana is available locally, and readiness checks verify observability. |
| Day 24 | Governance, PII anonymization, RBAC, encryption, OPA policy, compliance mapping | Lab 28 carries the governance layer as a platform concern: secrets are kept in `.env`, local artifacts are ignored, and fallback/error paths are explicit. |
| Day 25 | GPU FinOps, cost optimization, right-sizing, purchasing strategy, savings report | Lab 28 uses hybrid Local + Kaggle GPU to avoid always-on GPU spend and documents fallback mode as a cost-safe path. |
| Day 26 | MCP/A2A multi-agent routing, governance guard, audit logs, distributed tracing | Lab 28's API Gateway can act as the front door for future agentic routing; LangSmith trace IDs provide the traceability layer. |
| Day 27 | Data defense, stream checks, fault detection, cost/coverage tradeoff | Lab 28 smoke tests and production readiness checks act as the operational defense layer before demo. |

---

## Lab 28 ten integration points

| # | Lab 28 requirement | Runtime implementation | Prior-lab lineage |
|---:|---|---|---|
| 1 | Data ingestion -> Kafka | `scripts/01_ingest_to_kafka.py`, topic `data.raw` | Day 17 streaming/pipeline concepts |
| 2 | Kafka -> pipeline | `prefect/flows/kafka_to_delta.py` | Day 17 pipeline orchestration |
| 3 | Pipeline -> Lakehouse | parquet files under `delta-lake/raw` | Day 18 Delta/Lakehouse |
| 4 | Lakehouse -> Feature Store | `scripts/03_delta_to_feast.py`, Redis `feature:*` | Day 19 Feast/Redis feature store |
| 5 | Data -> Vector Store | `scripts/05_embed_to_qdrant.py`, Qdrant `documents` | Day 19 vector store |
| 6 | MLflow -> Model Registry | `scripts/06_register_model_mlflow.py`, `mlflow.db` | Day 21 MLOps/MLflow |
| 7 | Model -> vLLM/SGLang serving | Kaggle vLLM OpenAI-compatible server | Day 20 model serving, Day 25 GPU FinOps |
| 8 | Serving -> API Gateway | FastAPI `/api/v1/chat` | Day 20 serving integration |
| 9 | All -> Prometheus/Grafana | `/metrics`, Prometheus, Grafana | Day 23 observability stack |
| 10 | All -> LangSmith tracing | `lab28_chat_pipeline` run traces | Day 22 LLMOps tracing |

---

## Current verified status

Local fallback mode has already been verified:

```text
Production Readiness Score: 14/14 = 100%
Smoke tests: 8 passed
Prometheus metrics: OK
Grafana health: OK
LangSmith traces: OK
Kafka topics: OK
Redis feature store: OK
Qdrant vectors: OK
MLflow registry: OK
```

This proves the platform shell and integration flow.

---

## Remaining real-demo step

For the live demo, fallback mode must be replaced by real Kaggle GPU inference.

Required `.env` values:

```env
VLLM_TUNNEL_URL=https://<kaggle-vllm-tunnel>
EMBED_TUNNEL_URL=https://<kaggle-embedding-tunnel>
LANGCHAIN_API_KEY=<local-only-secret>
LANGCHAIN_PROJECT=lab28-platform
```

Expected real-demo API output:

```text
fallback_used: False
model: Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
error: null
context_items: 1..3
```

If `VLLM_TUNNEL_URL` is missing, Lab 28 intentionally returns `fallback-local` to keep the platform reliable during local smoke tests.

---

## Demo narrative

Use this framing in the final presentation:

1. Day 16-20 built the foundation: cloud/IaC, data pipeline, lakehouse, vector/feature store, and model serving.
2. Day 21-24 added operations: CI/CD, MLflow, LLMOps, observability, governance, and security.
3. Day 25-27 added platform judgment: FinOps, agentic routing/governance, and data-defense readiness.
4. Day 28 integrates all of them into one Local + Kaggle AI platform with Kafka, Prefect, lakehouse, Redis, Qdrant, vLLM, API Gateway, Prometheus/Grafana, LangSmith, MLflow, smoke tests, and readiness checks.
