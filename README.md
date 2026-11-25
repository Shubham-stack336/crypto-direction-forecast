# Crypto Direction

An educational project that forecasts whether a coin will be UP, DOWN or SIDEWAYS three hours from now, and keeps an
honest record of how often it was right. Not financial advice.

Built by Shubham Kumar: [LinkedIn](https://www.linkedin.com/in/shubham-kumar-30877a398/) ·
[GitHub](https://github.com/Shubham-stack336)

## What the models can and cannot do

Test data the models never saw, random forest, three classes (guessing scores 33.3% balanced accuracy):

| Model | Balanced accuracy | UP/DOWN direction right |
|---|---|---|
| Universal (ten unseen coins) | 37.8% | 52.1% (always the most common class: 51.7%) |

The models sense whether the market will move more than which way. Full numbers are in `backend/artifacts/*.metrics.json`
and on the Model page.

## Parts

- `ml_engine/` research and training
- `backend/` FastAPI (routes, controllers, services, repositories), PostgreSQL in production and SQLite locally
- `frontend/` React and TypeScript: Home, Forecast, Scanner, Coins, Model, About
- `streamlit_app.py` older daily-data demo, not part of the API (`backend/requirements-streamlit.txt`)

Production features: shared cache (memory or Redis), exchange failover with a circuit breaker, rate limits, background
market scan, one forecast per candle and model, model checksums and rollback, Prometheus metrics, optional Sentry, CI and
a weekly drift check.

## Run locally

```powershell
.\start-backend.bat          # http://127.0.0.1:8000
cd frontend; npm install; npm run dev   # http://localhost:5173
```

Tests: `cd backend; .\.venv\Scripts\python -m pytest -q` and `cd frontend; npm test`.
Deployment: [DEPLOYMENT.md](DEPLOYMENT.md).
