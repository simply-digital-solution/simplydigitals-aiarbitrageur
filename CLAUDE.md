# AI Arbitrageur — Claude Context

Intraday trading analytics app with Alpaca integration, real-time watchlists, multi-instrument charts, portfolio insights, and automated execution limits.

## Monorepo Structure

```
simplydigitals-aiarbitrageur/
├── simplydigitals-aiarbitrageur-api/   ← FastAPI backend (Python 3.11)
├── simplydigitals-aiarbitrageur-ui/    ← React + Vite frontend
├── .github/workflows/                  ← CI/CD pipelines
└── docker-compose.yml
```

## Backend (`simplydigitals-aiarbitrageur-api/`)

- **Framework**: FastAPI + SQLAlchemy (async) + Alembic migrations
- **Database**: SQLite (dev) / PostgreSQL (prod) via asyncpg/aiosqlite
- **Auth**: python-jose + passlib/bcrypt
- **External APIs**: Alpaca Trade API, yfinance
- **Observability**: structlog, prometheus-fastapi-instrumentator
- **Scheduler**: APScheduler

### App modules (`app/modules/`)
- `auth/` — authentication & JWT
- `broker/` — Alpaca broker integration
- `portfolio/` — portfolio management
- `prices/` — price data fetching (yfinance)
- `tickers/` — ticker/watchlist management
- `triggers/` — automated execution triggers

### Dev commands (from `simplydigitals-aiarbitrageur-api/`)
```bash
source .venv/bin/activate
ruff check . --select E,W,F,I,B,UP,N,ANN   # lint
mypy app/                                    # type check
bandit -r app/                               # security scan
pytest tests/ -v                             # run tests
alembic upgrade head                         # apply migrations
uvicorn app.main:app --reload --port 8001    # run dev server
```

### Code quality
- Linter: **Ruff** (line length 100, strict rules: E,W,F,I,B,UP,N,ANN)
- Type checker: **mypy** (strict mode)
- Security: **bandit**
- Test coverage minimum: 50% (`--cov-fail-under=50`)

## Frontend (`simplydigitals-aiarbitrageur-ui/`)

- **Framework**: React + Vite
- **Styling**: Tailwind CSS
- **Node version**: 18.x

### Dev commands (from `simplydigitals-aiarbitrageur-ui/`)
```bash
npm run dev -- --host 0.0.0.0 --port 5174   # run dev server
npm run lint                                  # ESLint
npm run format:check                          # Prettier check
npm run format                                # Prettier fix
npm run build                                 # production build
```

## CI/CD Pipelines

| Workflow | Trigger | Checks |
|---|---|---|
| `backend-ci.yml` | push/PR to api paths | ruff, mypy, bandit, pip-audit, pytest |
| `frontend-ci.yml` | push/PR to ui paths | eslint, prettier, vite build |
| `docker-build.yml` | push to main | Docker build + push to GHCR, Trivy scan |

**On push**: lint only. **On PR**: lint + tests/build.

## Docker

```bash
docker-compose up --build   # runs API on :8001, UI on :5174
```

Images pushed to GitHub Container Registry (`ghcr.io`).

## Environment

- Copy `simplydigitals-aiarbitrageur-api/.env.example` → `.env` for local dev
- `VITE_API_BASE_URL` needed for UI builds (defaults to `http://localhost:8000/api/v1`)
