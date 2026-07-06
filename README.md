# Lab #28 - Full Platform Integration Sprint

AI platform hybrid Local + Kaggle GPU. Mục tiêu là demo end-to-end từ data ingestion đến model serving với observability.

## Cross-day lineage

This Lab 28 submission consolidates the prior Day 16 to Day 27 work into one platform story.

Start with:

- [`docs/day16-day27-integration-map.md`](docs/day16-day27-integration-map.md)

That file maps each previous lab repository to the Lab 28 runtime, evidence, and demo narrative.

## Rubric focus

| Criteria | Weight | What this repo covers |
|---|---:|---|
| Integration Completeness | 40% | Kafka, Prefect, lakehouse parquet, Redis feature store, Qdrant, MLflow, vLLM, API Gateway |
| Observability | 25% | Prometheus metrics, Grafana health/dashboard, LangSmith tracing |
| Performance | 20% | Fast fallback path, latency budget for smoke tests, optional load profiling |
| Architecture Quality | 15% | Env-based config, graceful degradation, documented runbook |

## Architecture

```txt
Local Docker Compose:
  Data ingestion -> Kafka -> Prefect -> Delta Lake parquet
                         |            |
                         |            -> Redis Feature Store
                         -> Qdrant Vector Store

  API Gateway -> Qdrant context search -> Kaggle vLLM via cloudflared
              -> local fallback if Kaggle/tunnel is unavailable
              -> Prometheus/Grafana + LangSmith traces

Kaggle GPU:
  vLLM OpenAI-compatible server
  Embedding service
  cloudflared public tunnels
```

## 10 integration points

| # | Requirement | Implementation |
|---:|---|---|
| 1 | Data ingestion -> Kafka | `scripts/01_ingest_to_kafka.py` |
| 2 | Kafka -> pipeline | `prefect/flows/kafka_to_delta.py` |
| 3 | Pipeline -> Delta/Lakehouse | local parquet under `delta-lake/raw` |
| 4 | Lakehouse -> Feature Store | `scripts/03_delta_to_feast.py` pushes `feature:*` to Redis |
| 5 | Data -> Vector Store | `scripts/05_embed_to_qdrant.py` writes Qdrant `documents` |
| 6 | MLflow -> Model Registry | `scripts/06_register_model_mlflow.py` |
| 7 | Model -> vLLM serving | Kaggle vLLM single GPU |
| 8 | Serving -> API Gateway | FastAPI `/api/v1/chat` calls cloudflared URL |
| 9 | Components -> Prometheus/Grafana | `/metrics` scraped by Prometheus |
| 10 | Components -> LangSmith tracing | `lab28_chat_pipeline` traced when key is configured |

## Quick start local

```bash
cp .env.example .env
# fill VLLM_TUNNEL_URL, EMBED_TUNNEL_URL, and LANGCHAIN_API_KEY when available

docker compose up -d --build
docker compose ps
```

Open:

- API Gateway: http://localhost:8000
- API docs: http://localhost:8000/docs
- Prefect UI: http://localhost:4200
- Qdrant: http://localhost:6333/dashboard
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000, login `admin/admin`

## The 3 values you fill in `.env`

| `.env` name | Get it from | What it does |
|---|---|---|
| `VLLM_TUNNEL_URL` | Kaggle cloudflared tunnel for vLLM on port 8001 | API Gateway calls real LLM inference |
| `EMBED_TUNNEL_URL` | Kaggle cloudflared tunnel for embedding API on port 8002 | Qdrant script creates real embeddings |
| `LANGCHAIN_API_KEY` | LangSmith Settings -> API Keys | Sends traces to LangSmith |

Detailed step-by-step setup is in [`KAGGLE_SETUP.md`](KAGGLE_SETUP.md).

Safe defaults:

```env
LLM_TIMEOUT_SECONDS=1.2
ENABLE_LLM_FALLBACK=true
```

For smoke tests, fallback protects latency. For live demo with real model output, use `LLM_TIMEOUT_SECONDS=20`.

## Kaggle vLLM and embedding services

Use [`KAGGLE_SETUP.md`](KAGGLE_SETUP.md) to start both services:

```txt
Kaggle port 8001 -> cloudflared URL -> VLLM_TUNNEL_URL
Kaggle port 8002 -> cloudflared URL -> EMBED_TUNNEL_URL
```

Example local `.env` after Kaggle prints both URLs:

```env
VLLM_TUNNEL_URL=https://your-vllm-url.trycloudflare.com
EMBED_TUNNEL_URL=https://your-embed-url.trycloudflare.com
```

If `EMBED_TUNNEL_URL` is empty, `scripts/05_embed_to_qdrant.py` uses local deterministic embeddings, so smoke tests still work.

## LangSmith key

When you reach this step, create/copy a LangSmith API key from the LangSmith UI, then put it only in local `.env`:

```env
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_PROJECT=lab28-platform
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
```

Do not paste the key into GitHub or screenshots.

## Run the end-to-end demo

```bash
# 1. Ingest events
python scripts/01_ingest_to_kafka.py

# 2. Run Prefect flow once: Kafka -> parquet lakehouse
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 DELTA_LAKE_PATH=delta-lake/raw python prefect/flows/kafka_to_delta.py

# 3. Lakehouse -> Redis feature store
python scripts/03_delta_to_feast.py

# 4. Data -> Qdrant vector store
python scripts/05_embed_to_qdrant.py

# 5. Register fallback model metadata in MLflow
python scripts/06_register_model_mlflow.py

# 6. Call serving endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What is platform engineering?","embedding":[0.1]}'
```

For the curl embedding above, use a 384-length vector in a real call. Smoke tests already send the correct shape.

## Smoke tests

```bash
pytest smoke-tests/ -v
```

Expected: tests pass for critical user journeys:

1. Happy path chat request
2. API health
3. Kafka ingest + Qdrant seeded
4. Prometheus/Grafana observability
5. Failure path and Redis feature store

## Production readiness

```bash
python scripts/production_readiness_check.py
```

Target: `READY`, score greater than 80%.

## Screenshots to submit

Create these files before submission:

```txt
screenshots/prefect_ui.png
screenshots/api_gateway.png
screenshots/grafana_dashboard.png
smoke_tests_results.png
production_readiness.png
```

## Demo script

1. Architecture overview: explain Local + Kaggle + fallback.
2. Happy path: run ingestion, feature store, vector store, API call.
3. Error scenario: stop Kaggle/tunnel or leave URL empty, API still returns fallback.
4. Observability: show Prometheus/Grafana and LangSmith project.
5. Trade-off: reliability is prioritized with fallback; real vLLM is used when reachable.

## Submission answers

### 1. Trade-offs

The platform balances performance, reliability, and maintainability by keeping batch/data components decoupled from the serving path. Kaggle vLLM gives real GPU inference, while the local fallback keeps the API stable if the tunnel fails. Config lives in `.env`/Compose instead of hardcoded URLs.

### 2. Local-Kaggle disconnect

The API Gateway calls `VLLM_TUNNEL_URL`. If the tunnel times out or is missing, `ENABLE_LLM_FALLBACK=true` returns a local fallback answer. This is graceful degradation: the user gets a safe response and the service remains healthy.

### 3. Kafka decoupling

Data ingestion only writes immutable events to `data.raw`. The pipeline consumes those events independently. New consumers, such as feature store or vector indexing jobs, can be added without changing the producer.

### 4. Observability

Prometheus scrapes `/metrics` from the API Gateway. Grafana visualizes service health and API metrics. LangSmith traces the `lab28_chat_pipeline` so request latency, fallback usage, and LLM calls can be inspected.

### 5. Service crash handling

If Qdrant fails, API Gateway continues with empty context. If Kaggle/vLLM fails, fallback responds. If Kafka is unavailable, ingestion retries and readiness check fails fast. Redis/Qdrant/Kafka checks are automated in `production_readiness_check.py`.
