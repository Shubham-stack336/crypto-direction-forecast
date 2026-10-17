# Crypto Direction Forecast

Educational project: predicts whether BTC/USDT will go **UP**, **DOWN** or stay **SIDEWAYS** over the next 3 hourly candles.
It is **not financial advice** and makes no claim about trading profit.

```
ml_engine/   research code: data collection, features, labels, training, walk-forward evaluation, tests
backend/     FastAPI service (Routes -> Controllers -> Services -> Repositories) + PostgreSQL history
frontend/    React + TypeScript + Vite dashboard
render.yaml  Render Blueprint (API + PostgreSQL)
DEPLOYMENT.md  step-by-step deployment guide (Hinglish)
```

## How good is the model? (measured, not promised)

Final untouched test period, 2,613 hourly samples (2026-06-30 to 2026-10-17), random forest trained on earlier data only:

| | Accuracy | Balanced accuracy | Macro F1 | UP/DOWN direction right |
|---|---|---|---|---|
| Random forest (used) | 0.486 | 0.399 | 0.397 | 0.546 |
| Logistic regression | 0.510 | 0.378 | 0.368 | 0.508 |
| Naive: always SIDEWAYS | 0.544 | 0.333 | 0.235 | n/a |

- Walk-forward validation (5 folds, earlier data): random forest balanced accuracy 0.405 (std 0.014), logistic regression 0.392 (std 0.014); random guessing is 0.333.
- Diagnostics showed most of that edge comes from **volatility** (will the market move?), not **direction**. A model using only `vol_10` got 0.381 balanced accuracy with a 0.508 direction hit rate.
- The random forest narrowly missed the pre-registered improvement rule over logistic regression (+0.0135 vs required +0.014); it was kept as the candidate because it won every fold and was never worse. This is recorded in `ml_engine/data/experiments.jsonl`.
- Probabilities are **not calibrated**. A good classification score does not mean a trading strategy would be profitable after fees and slippage.

## Run locally

Backend (Python 3.11):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env          # optionally set APP_DATABASE_URL to a PostgreSQL URL
alembic upgrade head            # only if APP_DATABASE_URL is set
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
python -m pytest -q             # starts a throw-away PostgreSQL via pgserver for the DB tests
```

Frontend (Node 20+):

```powershell
cd frontend
npm install
copy .env.example .env          # VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev                     # http://localhost:5173
npm test
npm run build
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | process is up |
| GET | `/health/ready` | a model is loaded and, if configured, the database answers |
| GET | `/api/v1/market/{symbol}` | latest closed candles and data freshness (`BTC-USDT`) |
| POST | `/api/v1/predictions/{symbol}` | run the model on live candles, save to history |
| GET | `/api/v1/predictions/{symbol}/history?limit=&offset=` | saved forecasts, newest first |
| GET | `/api/v1/models/{symbol}/status` | model metadata and saved evaluation metrics |

## Retraining

```powershell
cd ml_engine
python scripts/step2_collect.py     # collect candles (writes data/raw + metadata)
python scripts/step12_final.py      # train, evaluate once on the held-out test, save artifacts/
```

Copy the new `ml_engine/artifacts/*` into `backend/artifacts/`, commit and push; Render redeploys.
Only retrain on data that ends before the evaluation period you intend to report.
