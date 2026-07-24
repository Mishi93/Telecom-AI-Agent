# Telecom Admin Frontend (React + TypeScript + Tailwind + Ant Design)

Replaces admin_app.py, customer_dashboard.py, and analytics.py (as one app with 3 sidebar pages).

## Local dev
```
npm install
cp .env.example .env      # edit VITE_BACKEND_URL if needed
npm run dev
```

## Deploy on Railway
1. New service, Root Directory = this folder's path in your repo (e.g. `admin-frontend`)
2. Build Command: `npm install && npm run build`
3. Start Command: `npx vite preview --host 0.0.0.0 --port $PORT`
   (or serve `dist/` with any static file server - `vite preview` is fine for this scale)
4. Set env var: `VITE_BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8080`
   (Vite env vars are baked in at BUILD time, not runtime - if you change this
   var, you must trigger a rebuild, not just a restart)

## Backend endpoints this app expects
Standard CRUD: GET/POST /customers, GET/PUT/DELETE /customers/{id},
GET /customers/{id}/complaints, GET /predict/churn/{id},
GET /predict/package/{id}, GET /analytics/summary

New (not yet in the FastAPI backend as of this build - add these to use the
Knowledge Base tab):
- POST /rag/upload (multipart file upload)
- POST /rag/reindex

Analytics also optionally reads `open_tickets` / `resolved_tickets` fields
from /analytics/summary - if your backend doesn't return them yet, the UI
derives them from complaints_by_status as a fallback.
