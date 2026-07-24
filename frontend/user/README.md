# Telecom Customer Chat Frontend (React + TypeScript + Tailwind + Ant Design)

Replaces user_app.py.

## Local dev
```
npm install
cp .env.example .env      # edit VITE_BACKEND_URL if needed
npm run dev
```

## Deploy on Railway
1. New service, Root Directory = this folder's path in your repo (e.g. `user-frontend`)
2. Build Command: `npm install && npm run build`
3. Start Command: `npx vite preview --host 0.0.0.0 --port $PORT`
4. Set env var: `VITE_BACKEND_URL=http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:8080`

## Note: improvement over the original Streamlit app
The original user_app.py always sent an empty `history: []` array to
POST /chat, so the agent had no memory of earlier turns in the same
conversation. This version sends the full accumulated history each turn,
which your backend's /chat endpoint already supports.

## Backend endpoints this app expects
GET /customers, POST /chat
