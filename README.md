# simplydigitals-aiarbitrageur

AI Arbitrageur is an intraday trading analytics app with Alpaca integration, real-time watchlists, multi-instrument charts, portfolio insights, and automated execution limits.

## Structure

```
simplydigitals-aiarbitrageur/
├── simplydigitals-aiarbitrageur-api/   ← FastAPI backend
├── simplydigitals-aiarbitrageur-ui/    ← React frontend
├── docker-compose.yml
└── README.md
```

## Quick Start

### API

```bash
cd simplydigitals-aiarbitrageur/simplydigitals-aiarbitrageur-api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### UI

```bash
cd simplydigitals-aiarbitrageur/simplydigitals-aiarbitrageur-ui
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

Open the UI at `http://localhost:5174`.

## Docker

```bash
cd simplydigitals-aiarbitrageur
docker-compose up --build
```

API: http://localhost:8001
UI: http://localhost:5174
