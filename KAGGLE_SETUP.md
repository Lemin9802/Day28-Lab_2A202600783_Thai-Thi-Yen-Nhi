# Kaggle setup guide for Lab28

This guide explains the 3 environment values used by the local `.env` file.

## What you need to fill

| `.env` name | Where it comes from | Required? | Meaning |
|---|---|---:|---|
| `VLLM_TUNNEL_URL` | Kaggle cloudflared tunnel for vLLM, port 8001 | Yes for real model demo | Local API Gateway calls this URL for LLM inference |
| `EMBED_TUNNEL_URL` | Kaggle cloudflared tunnel for embedding API, port 8002 | Optional | Qdrant script calls this URL to create embeddings |
| `LANGCHAIN_API_KEY` | LangSmith Settings -> API Keys | Yes for LangSmith tracing | Sends request traces to LangSmith project |

If `VLLM_TUNNEL_URL` is empty or slow, the API Gateway still works because `ENABLE_LLM_FALLBACK=true`.

If `EMBED_TUNNEL_URL` is empty, the Qdrant script uses local deterministic embeddings, so smoke tests still work.

## Step 1 - Create Kaggle notebook

1. Open Kaggle.
2. Create a new Notebook.
3. Enable GPU in notebook settings.
4. Enable Internet.
5. Run the cells below in order.

## Step 2 - Install dependencies

```python
!pip install -q --upgrade pip
!pip install -q vllm fastapi uvicorn transformers

!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
!chmod +x cloudflared
!./cloudflared --version
```

## Step 3 - Start vLLM server on port 8001

```python
import subprocess, time, requests

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"

!pkill -f "vllm" || true

cmd = [
    "python", "-m", "vllm.entrypoints.openai.api_server",
    "--model", MODEL_NAME,
    "--host", "0.0.0.0",
    "--port", "8001",
    "--max-model-len", "2048",
    "--gpu-memory-utilization", "0.85",
    "--trust-remote-code",
]

log_file = open("vllm_server.log", "w")
vllm_proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, text=True)

print("Started vLLM process PID:", vllm_proc.pid)
print("Waiting for vLLM /health ...")

ready = False
for i in range(90):
    try:
        r = requests.get("http://localhost:8001/health", timeout=3)
        if r.status_code == 200:
            ready = True
            print("vLLM READY on http://localhost:8001")
            break
    except Exception:
        pass
    time.sleep(5)
    if i % 6 == 0:
        print(f"still loading... {i*5}s")

if not ready:
    print("vLLM NOT READY yet. Last logs:")
    !tail -80 vllm_server.log
```

## Step 4 - Test vLLM locally inside Kaggle

```python
import requests, json, time

payload = {
    "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
    "messages": [{"role": "user", "content": "Reply with one short sentence: Lab 28 real vLLM is working."}],
    "temperature": 0.2,
    "max_tokens": 64,
}

start = time.time()
resp = requests.post("http://localhost:8001/v1/chat/completions", json=payload, timeout=60)
print("status:", resp.status_code)
print("latency_sec:", round(time.time() - start, 2))
print(json.dumps(resp.json(), indent=2)[:2000])
```

Expected: `status: 200` and a non-empty `choices[0].message.content`.

## Step 5 - Start embedding API on port 8002

This implementation uses `transformers` directly instead of importing `sentence_transformers`. This avoids Kaggle/PyTorch/TorchCodec compatibility errors while still returning 384-dimensional MiniLM embeddings.

```python
!pkill -f "uvicorn.*8002" || true
```

```python
%%writefile embed_server.py
from fastapi import FastAPI
from pydantic import BaseModel
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

app = FastAPI(title="Lab28 Embedding Service")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
device = "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME).to(device)
model.eval()

class EmbedRequest(BaseModel):
    texts: list[str]

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "dim": 384}

def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output.last_hidden_state
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

@app.post("/embed")
def embed(payload: EmbedRequest):
    encoded = tokenizer(
        payload.texts,
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        output = model(**encoded)
        vectors = mean_pooling(output, encoded["attention_mask"])
        vectors = F.normalize(vectors, p=2, dim=1)

    return {"embeddings": vectors.cpu().tolist()}
```

```python
import subprocess, threading, time, requests

def run_embed_api():
    subprocess.run(["uvicorn", "embed_server:app", "--host", "0.0.0.0", "--port", "8002"])

threading.Thread(target=run_embed_api, daemon=True).start()

for i in range(40):
    try:
        r = requests.get("http://localhost:8002/health", timeout=3)
        if r.status_code == 200:
            print("Embedding API READY")
            print(r.json())
            break
    except Exception:
        pass
    time.sleep(3)
    if i % 5 == 0:
        print("waiting embed api...", i * 3)
```

## Step 6 - Create cloudflared URL for vLLM

```python
import subprocess, re

vllm_proc = subprocess.Popen(
    ["./cloudflared", "tunnel", "--url", "http://localhost:8001"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

VLLM_TUNNEL_URL = None
for line in vllm_proc.stdout:
    print(line, end="")
    match = re.search(r"https://[-a-zA-Z0-9.]+trycloudflare.com", line)
    if match:
        VLLM_TUNNEL_URL = match.group(0)
        print("\nCOPY THIS TO LOCAL .env:")
        print("VLLM_TUNNEL_URL=" + VLLM_TUNNEL_URL)
        break
```

Copy the printed value into local `.env`, for example:

```env
VLLM_TUNNEL_URL=https://your-vllm-url.trycloudflare.com
```

## Step 7 - Create cloudflared URL for embedding API

```python
import subprocess, re

embed_proc = subprocess.Popen(
    ["./cloudflared", "tunnel", "--url", "http://localhost:8002"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

EMBED_TUNNEL_URL = None
for line in embed_proc.stdout:
    print(line, end="")
    match = re.search(r"https://[-a-zA-Z0-9.]+trycloudflare.com", line)
    if match:
        EMBED_TUNNEL_URL = match.group(0)
        print("\nCOPY THIS TO LOCAL .env:")
        print("EMBED_TUNNEL_URL=" + EMBED_TUNNEL_URL)
        break
```

Copy the printed value into local `.env`, for example:

```env
EMBED_TUNNEL_URL=https://your-embed-url.trycloudflare.com
```

## Step 8 - Test public tunnels from Kaggle

```python
import requests, json, time

vllm_payload = {
    "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
    "messages": [{"role": "user", "content": "Reply with exactly: public tunnel works"}],
    "temperature": 0.2,
    "max_tokens": 32,
}

start = time.time()
r1 = requests.post(f"{VLLM_TUNNEL_URL}/v1/chat/completions", json=vllm_payload, timeout=60)
print("vLLM status:", r1.status_code)
print("vLLM latency_sec:", round(time.time() - start, 2))
print(json.dumps(r1.json(), indent=2)[:1200])

r2 = requests.post(f"{EMBED_TUNNEL_URL}/embed", json={"texts": ["Lab 28 embedding tunnel works"]}, timeout=30)
print("embed status:", r2.status_code)
print("embed dim:", len(r2.json()["embeddings"][0]))
```

Expected:

```text
vLLM status: 200
embed status: 200
embed dim: 384
```

## Step 9 - Get LangSmith key

1. Open LangSmith.
2. Go to Settings.
3. Open API Keys.
4. Create a new key.
5. Copy the key into local `.env`.

Example:

```env
LANGCHAIN_API_KEY=your_real_key_here
LANGCHAIN_PROJECT=lab28-platform
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
```

Do not paste the real key into ChatGPT, GitHub, screenshots, or README.

## Final `.env` shape

```env
VLLM_TUNNEL_URL=https://your-vllm-url.trycloudflare.com
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4
LLM_TIMEOUT_SECONDS=20
ENABLE_LLM_FALLBACK=true
EMBED_TUNNEL_URL=https://your-embed-url.trycloudflare.com
LANGCHAIN_API_KEY=your_real_langsmith_key
LANGCHAIN_PROJECT=lab28-platform
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
API_GATEWAY_URL=http://localhost:8000
PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DELTA_LAKE_PATH=delta-lake/raw
```

For smoke tests, keep `LLM_TIMEOUT_SECONDS=1.2` so fallback protects latency. For a live demo with real vLLM output, use `LLM_TIMEOUT_SECONDS=20`.
