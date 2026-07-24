# Telecom AI Agent

An AI-powered telecom customer support platform: a LangChain/Groq-driven chat
agent with tool-calling (account lookups, complaint filing, RAG-backed
knowledge base search), ML-driven churn/plan-recommendation predictions, and
two separate frontends — an internal admin/staff portal and a customer-facing
chat app.

## Architecture

```
telecom/
├── backend/            FastAPI + LangChain agent + SQLite + Chroma + ML models
├── admin-frontend/      React/TS/Tailwind/AntD - staff-facing
└── user-frontend/       React/TS/Tailwind/AntD - customer-facing chat
```

Three independently deployable services, all talking to the one backend API.

### Backend (`backend/`)

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app: customer CRUD, chat endpoint, ML prediction endpoints, analytics |
| `agent/core.py` | LangChain + Groq (`llama-3.3-70b-versatile`) agent, tool binding, system prompt |
| `agent/tools.py` | Tool-calling functions: `check_balance`, `register_complaint`, `check_complaint_status`, `search_knowledge_base` |
| `database/` | SQLAlchemy models (`Customer`, `Complaint`) and engine/session setup |
| `rag/` | Chroma vector store + retriever, using HF Inference Providers (`router.huggingface.co`) for embeddings |
| `ml_models/` | Trained churn (XGBoost) and plan-tier (Random Forest) classifiers + inference wrapper |
| `data_pipeline/` | Synthetic data generator and model training scripts |

### Frontends

- **`admin-frontend/`** — Register/Update/Delete customers, Knowledge Base document upload + reindex, Customer Dashboard (profile + complaints + ML predictions), Analytics (charts across all customers).
- **`user-frontend/`** — Customer-facing chat interface, sends full conversation history to the agent each turn.

## Local Development

### Prerequisites
- Python 3.11+
- Node 18+
- A [Groq API key](https://console.groq.com/keys)
- A [Hugging Face token](https://huggingface.co/settings/tokens) (for embeddings)

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
cp .env.example .env           # then fill in real values, see below
```

Generate sample data and train the ML models (first run only, or whenever
you want to regenerate):
```bash
python data_pipeline/generate_training_data.py
python data_pipeline/train_models.py
```

Build the RAG knowledge base (optional, needs PDFs/CSVs in `data_pipeline/data/`):
```bash
python rag/ingest_rag.py
```

Run the API:
```bash
uvicorn app.main:app --reload
```
API available at `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### 2. Admin frontend

```bash
cd admin-frontend
npm install
cp .env.example .env           # defaults to http://127.0.0.1:8000, edit if needed
npm run dev
```
Runs at `http://localhost:5173`.

### 3. User (chat) frontend

```bash
cd user-frontend
npm install
cp .env.example .env
npm run dev
```
Runs at `http://localhost:5174`.

## Environment Variables

### `backend/.env`
| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for the LLM |
| `HF_TOKEN` | Yes (for RAG) | Hugging Face token for embeddings via Inference Providers |
| `TELECOM_DB_PATH` | Prod only | Absolute path to the SQLite file (e.g. `/data/telecom.db` on a Railway Volume). Falls back to a local relative path if unset. |
| `DATABASE_URL` | Prod only | Full SQLAlchemy URL matching `TELECOM_DB_PATH`, e.g. `sqlite:////data/telecom.db` (4 slashes). Falls back to `sqlite:///./telecom.db` if unset. |
| `VECTOR_STORE_DIR` | Prod only | Absolute path for the Chroma vector store (e.g. `/data/vector_store`). Falls back to a local path if unset. |

**`TELECOM_DB_PATH` and `DATABASE_URL` must point at the same file** — the
first is used by the data-generation/training scripts, the second by the
running app. A mismatch between them is the single most common source of
"no such table: customers" errors.

### `admin-frontend/.env` and `user-frontend/.env`
| Variable | Description |
|---|---|
| `VITE_BACKEND_URL` | Backend API base URL. Defaults to `http://127.0.0.1:8000` locally. Baked in at **build time** — changing it requires a rebuild, not just a restart. |

## Deploying on Railway

Three services, one GitHub repo, different Root Directory + Start Command each:

| Service | Root Directory | Start Command |
|---|---|---|
| `backend` | `backend` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `admin-portal` | `admin-frontend` | `npm install && npm run build && npx vite preview --host 0.0.0.0 --port $PORT` |
| `customer-chat` | `user-frontend` | `npm install && npm run build && npx vite preview --host 0.0.0.0 --port $PORT` |

### Setup steps
1. **Create the 3 services** from your repo as above.
2. **Pin a static port** on `backend` (Variables tab): `PORT=8080` (or your choice — just be consistent everywhere below).
3. **Add a Volume** to `backend` (Settings → Volumes), e.g. mounted at `/data`. Required for SQLite and the Chroma index to survive redeploys — Railway's default filesystem is ephemeral.
4. **Set `backend`'s env vars**:
   ```
   PORT=8080
   GROQ_API_KEY=...
   HF_TOKEN=...
   TELECOM_DB_PATH=/data/telecom.db
   DATABASE_URL=sqlite:////data/telecom.db
   VECTOR_STORE_DIR=/data/vector_store
   ```
5. **Set both frontends' env vars**:
   ```
   VITE_BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8080
   ```
   (Railway private networking — internal only, `http://` not `https://`.)
6. **Populate the database** once, via `railway ssh` into `backend`:
   ```
   cd /app   # confirm with pwd/ls first
   python data_pipeline/generate_training_data.py
   python data_pipeline/train_models.py
   python rag/ingest_rag.py   # optional, for the knowledge base
   ```
7. **Generate public domains** for `backend` (optional, for testing), `admin-portal`, and `customer-chat` (Settings → Networking).
8. **Update backend's CORS allow-list** in `main.py` to include your deployed frontend URLs, then redeploy:
   ```python
   allow_origins=[
       "http://localhost:5173", "http://127.0.0.1:5173",
       "http://localhost:5174", "http://127.0.0.1:5174",
       "https://admin-portal-production-xxxx.up.railway.app",
       "https://customer-chat-production-xxxx.up.railway.app",
   ]
   ```

### Known deployment gotchas (learned the hard way)
- **Volumes support one active mount at a time** — keep `backend` at 1 replica.
- **`railway run` executes locally** (with remote env vars injected), not inside the deployed container — use `railway ssh` when you need to touch the container's actual filesystem/Volume.
- Editing env vars only takes effect on the **next** container start — a stale `railway ssh` session won't see a variable you just added; exit and reconnect.
- `VITE_*` env vars are baked in at **build time** — changing them requires a rebuild, not just a restart.

## Machine Learning Models — Important Caveat

Both `churn_xgb.pkl` (XGBoost) and `package_rf.pkl` (Random Forest) are
currently trained on **rule-derived labels**, not real historical outcomes:
- **Churn**: labeled "at risk" if a customer has 2+ complaints that are both `status=Open` and `priority=High`.
- **Package tier**: labeled via a scoring rule over data allowance, minutes, and balance.

This means the models will report high accuracy (since the label is a
near-deterministic function of the input features) but this is **not**
evidence of real predictive power — it validates the pipeline works, not
that it predicts real customer behavior. Replace `build_churn_label()` and
`build_tier_label()` in `data_pipeline/train_models.py` with real historical
outcomes (actual churn events, actual upgrade/downgrade history) as soon as
that data exists, then retrain.

## Security Notes

- Rotate any API key that was ever hardcoded in source or committed to git history — treat it as compromised regardless of whether you can point to actual misuse.
- Never commit `.env` files — only `.env.example` templates with placeholder values.