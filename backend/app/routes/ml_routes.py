"""ML & Model Evaluation Routes.

Endpoints for training models, comparing against naive baseline, and running direction forecasts.
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.model_service import ModelService

router = APIRouter(prefix="/api/v1/ml", tags=["Machine Learning"])
model_service = ModelService()


@router.post("/train/{symbol}")
def train_and_evaluate_models(
    symbol: str,
    train_ratio: float = Query(0.8, ge=0.5, le=0.9, description="Chronological train split ratio"),
):
    """Train all models (Baseline, Logistic, Random Forest, Gradient Boosting) using time-based split."""
    try:
        summary = model_service.train_and_compare_all(symbol=symbol, train_ratio=train_ratio)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.get("/compare/{symbol}")
def get_model_comparison(symbol: str):
    """Retrieve evaluation metrics comparison table against naive baseline."""
    try:
        summary = model_service.train_and_compare_all(symbol=symbol)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get comparison: {str(e)}")


@router.get("/predict/{symbol}")
def predict_next_day(symbol: str):
    """Generate next-day direction prediction (UP / DOWN) with confidence and probabilities."""
    try:
        forecast = model_service.predict_next_day(symbol=symbol)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
