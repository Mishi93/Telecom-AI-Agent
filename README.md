# Telecom AI Agent

An AI-powered telecom customer support platform: a LangChain / Groq chat agent with RAG and tool-calling, ML models for churn and plan-tier prediction, and separate admin and customer React interfaces — all backed by a FastAPI service.


> Built by a telecom engineer (NED University, Karachi) as an end-to-end applied-AI project: the same stack a telecom support team would actually use — chat, knowledge base, customer records, complaints and predictions — in one repo.

## What it does

- **Customer chat** — a user asks about their balance, data/minutes left, a plan or a policy, or raises a complaint. The agent answers from the knowledge base or acts on the customer's real record via tools.
- **Admin portal** — view customers, complaints and analytics, and manage the knowledge base.
- **Churn prediction** — XGBoost model predicting whether a customer is at risk.
- **Plan-tier recommendation** — Random Forest model recommending Basic / Standard / Premium.
- **RAG knowledge base** — FAQ, internet packages and a telecom policy handbook, searchable by the agent with sources.

## Architecture

```
Telecom-AI-Agent/
├── backend/
│   ├── app/main.py              # FastAPI app — all 14 endpoints + /docs
│   ├── app/config.py            # Settings (see note below)
│   ├── agent/core.py            # ChatGroq agent, tools bound
│   ├── agent/tools.py           # check_balance, register_complaint,
│   │                            # check_complaint_status, search_knowledge_base
│   ├── database/                # SQLAlchemy models + connection (SQLite)
│   ├── data_pipeline/data/      # Synthetic data generator + RAG corpus
│   │                            # (FAQ's.csv, internet_packages.csv,
│   │                            #  NEXIS_Telecom_Policy_Handbook.pdf)
│   ├── ml_models/               # Training + predictors, saved .pkl models
│   ├── rag/                     # Ingest + Chroma retriever
│   └── requirements.txt
├── frontend/
│   ├── admin/                   # Vite + React + TypeScript, port 5173
│   └── user/                    # Vite + React + TypeScript, port 5174
├── .gitignore
└── README.md
```

Three services when deployed: backend, admin portal, customer chat.

## The chat agent

- **Model:** `llama-3.3-70b-versatile` via Groq (`ChatGroq`), temperature 0.
- **Tools (4, bound with `llm.bind_tools`):**

  | Tool | What it does |
  | --- | --- |
  | `check_balance` | Customer name, balance, data and minutes remaining |
  | `register_complaint` | Creates a complaint ticket (`CMP-<year>-<8 hex>`, status Open). Categories: Billing / Network / Technical / Other, default priority Medium. Asks follow-up questions if category or description is missing |
  | `check_complaint_status` | Status of a customer's complaint |
  | `search_knowledge_base` | RAG search over FAQs, packages and the policy handbook, with source-tagged results |

- **Tool loop:** hand-written in `main.py`, up to 5 rounds. There is no AgentExecutor or LangGraph.
- **System prompt:** use tools for balances, quotas and tickets; use RAG for plans and policies; never guess policy; never expose raw JSON.
- **History:** `POST /chat` accepts a message plus the conversation history (`{role, content}` turns); `customer_id` is optional. The user frontend sends the full accumulated history; on error the API returns a fallback message ("I couldn't process your request. Please try again.").

A fifth tool, `lookup_telecom_knowledge_base`, is defined in `tools.py` but is **not** bound in `core.py`, so the agent cannot call it.

## API

FastAPI, docs at `/docs` when running. All 14 routes:

| Method & path | What it does |
| --- | --- |
| `GET /` | Service root |
| `GET /customers` | List customers (customer_id + name) |
| `GET /customers/{customer_id}` | One customer |
| `POST /customers` | Create customer (201; 400 if the customer already exists) |
| `PUT /customers/{customer_id}` | Update customer |
| `DELETE /customers/{customer_id}` | Delete customer |
| `GET /customers/{customer_id}/complaints` | That customer's complaints |
| `POST /customers/{customer_id}/complaints` | Create a complaint ticket |
| `GET /analytics/summary` | Totals and breakdowns — see note below |
| `GET /predict/churn/{customer_id}` | Churn risk: `churn_risk`, `churn_probability`, label At Risk / Stable (404 if customer missing) |
| `GET /predict/package/{customer_id}` | Recommended package tier + probability |
| `POST /chat` | Chat agent — returns `response` and `tool_calls` |
| `POST /rag/upload` | Upload a `.pdf` / `.csv` / `.txt` file, save it to the corpus and rebuild the vector store |
| `POST /rag/reindex` | Rebuild the vector store from the corpus |

**Note on `/analytics/summary`:** total customers, total complaints, open/resolved ticket counts and the complaints breakdowns are real database counts. But `churn_risk_distribution` (Stable 85%, At Risk 15%) and `package_tier_distribution` (Basic 50%, Standard 30%, Premium 20%) are **hardcoded proportions of the total**, not model outputs. Also, the "In Progress" status count is seeded at 0 and never incremented by the counting loop, so it always reads 0.

## ML models

Both models are trained in `backend/ml_models/train_models.py` on **synthetic data** — 260 customers generated with Faker (seed 42), with complaint types Billing / Network / Technical / Package and priorities Low / Medium / High.

**Labels are rule-based, not real outcomes** (the training file's own docstring says so):

- **Churn = 1** if the customer has 2+ complaints that are both Open and High priority.
- **Package tier** from a score: +2 if data ≥ 25 GB or unlimited, +1 if ≥ 5 GB, +2 if minutes ≥ 1000, +1 if ≥ 300, +1 if balance ≥ 80. Score ≥ 4 → Premium, ≥ 2 → Standard, otherwise Basic.

Features (8): `balance`, `data_gb`, `has_unlimited`, `minutes_remaining`, `total_complaints`, `open_complaints`, `high_priority_complaints`, `billing_complaints`.

| Task | Model | Settings |
| --- | --- | --- |
| Churn | XGBoost `XGBClassifier` | n_estimators=150, max_depth=4, learning_rate=0.1, eval_metric=logloss, random_state=42 |
| Package tier | Random Forest `RandomForestClassifier` | n_estimators=200, max_depth=8, random_state=42 |

Split: 80% train / 20% test, stratified, `random_state=42`. The training script only prints a classification report — **no accuracy number is stored in the repo, so none is quoted here.** Because the labels are rule-derived, a high score would validate that the pipeline works, not that it predicts real customer behaviour. The trained models are committed as `backend/ml_models/saved/churn_xgb.pkl` and `saved/package_rf.pkl`.

## RAG knowledge base

- **Corpus:** `backend/data_pipeline/data/` — `FAQ's.csv`, `internet_packages.csv`, `NEXIS_Telecom_Policy_Handbook.pdf`.
- **Ingest:** PDFs loaded per page (`PyPDFLoader`), CSVs per row (`CSVLoader`); split with `RecursiveCharacterTextSplitter` (chunk size 800, overlap 120); stored in Chroma under `backend/rag/vector_store/` (not committed — ignored in `.gitignore`).
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` via `HuggingFaceEndpointEmbeddings`.
- **Retrieval:** top 4 chunks (`k=4`), returned as source-tagged chunks such as `[Result n - source: ... (page n)]`. `search_knowledge_base` raises an error if the store has not been ingested yet — run the ingest step first.
- **Note:** `VECTOR_STORE_DIR` is hardcoded in `retriever.py` as `rag/vector_store` relative to that file. Setting the `VECTOR_STORE_DIR` environment variable has no effect.

## Frontends

Both are Vite + React 18 + TypeScript + Tailwind CSS + Ant Design + axios.

| App | Folder | Port | Pages |
| --- | --- | --- | --- |
| Admin portal | `frontend/admin/` | 5173 | AdminPortal, Analytics, CustomerDashboard |
| Customer chat | `frontend/user/` | 5174 | Single-page chat |

The admin app also uses `@ant-design/plots` and `react-router-dom`; the user app does not. Note the Vite versions differ between the two apps (admin `^5.4.10`, user `^8.1.5`).

## Run it locally

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` manually — **there is no `backend/.env.example` in the repo**, so do not try to copy one:

```env
GROQ_API_KEY=your-groq-key
HF_TOKEN=your-hugging-face-token
DATABASE_URL=sqlite:///./telecom.db
```

`GROQ_API_KEY` is required (the agent raises an error without it). `HF_TOKEN` is required for RAG. `DATABASE_URL` defaults to local SQLite if omitted.

Then generate data, train the models and ingest the knowledge base:

```bash
python data_pipeline/data/generate_training_data.py
python ml_models/train_models.py
python rag/ingest_rag.py   # optional, but RAG search needs it
uvicorn app.main:app --reload
```

API at http://127.0.0.1:8000, docs at http://127.0.0.1:8000/docs. Tables are created at startup.

### 2. Frontends

```bash
cd frontend/admin   # or frontend/user
npm install
cp .env.example .env
npm run dev
```

Admin at http://localhost:5173, user chat at http://localhost:5174. Each `.env.example` contains only `VITE_BACKEND_URL=http://127.0.0.1:8000` (plus a placeholder production URL). `VITE_BACKEND_URL` is baked in at build time, so set it before building for deployment.

## Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Groq console key for the chat agent |
| `HF_TOKEN` | Yes, for RAG | Hugging Face token for embeddings |
| `DATABASE_URL` | No | Defaults to `sqlite:///./telecom.db` |
| `TELECOM_DB_PATH` | No | Used by the data / training scripts; defaults to repo-root `telecom.db` |
| `VITE_BACKEND_URL` | No | Frontend API URL; defaults to `http://127.0.0.1:8000` |
| `VECTOR_STORE_DIR` | — | Documented in older docs but **ignored by the code** (see RAG) |
| `PORT` | On Railway | Backend start uses `$PORT` (8080 in the deployment notes) |



## Screenshots



## Technologies

- **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy (SQLite), Pydantic
- **AI:** LangChain, Groq (`llama-3.3-70b-versatile`), Hugging Face embeddings (`all-MiniLM-L6-v2`), Chroma
- **ML:** scikit-learn, XGBoost, joblib, pandas, Faker (synthetic data)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Ant Design, axios

## Security

- Never commit `.env` or any API key. `backend/.env` is git-ignored; keep it that way.
- The code comments note that a Groq key and a Hugging Face token were previously exposed in source control. **If a key was ever committed, rotate it in the Groq / Hugging Face console** — removing it from the code does not purge git history. The current `backend/app/config.py` has an empty default for `GROQ_API_KEY` and no secret is hardcoded in the main repo.
- There is no authentication on any endpoint, including `POST /rag/upload` and `DELETE /customers/{id}`. Do not expose the backend publicly without adding auth.


## Ideas for next steps

- Add a small test suite — at minimum, the prediction endpoints with the committed `.pkl` files, and the chat fallback path.
- Add a licence and a `backend/.env.example` (with placeholder values only).
- Fix the hardcoded `/analytics/summary` distributions to use real model predictions, and fix the "In Progress" count.
- Bind or remove `lookup_telecom_knowledge_base`, and either use `config.py` or remove it (with its missing `pydantic-settings` dependency).
- Add authentication before any public deployment, and align the two frontends' Vite versions.
- Deploy the three Railway services, verify each serves, and add the real live URLs at the top of this README.

