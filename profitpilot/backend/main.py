"""
backend/main.py

FastAPI app tying together strategy_service, trading_service, and self_learning.
Provides routes:
- POST /trade         -> run strategy and optionally execute (dry_run default true)
- POST /train         -> train incremental model with provided features+labels
- POST /predict       -> predict score for a feature vector
- GET  /orders        -> list in-memory orders
- GET  /portfolio     -> list in-memory portfolio
- GET  /strategies    -> list available strategies

Auth is optional for dev; use Authorization: Bearer <token> to access protected endpoints.
"""

import os
import uvicorn
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Body, Depends, Query
from pydantic import BaseModel

from .strategy_service import default_strategy_manager
from .trading_service import evaluate_and_trade, list_orders, get_portfolio
from .self_learning import train_on_batch, predict_from_features
from .auth_utils import get_current_user

app = FastAPI(title="ProfitPilotAI Backend", version="0.1")

# Pydantic models
class TradeRequest(BaseModel):
    strategy: str
    market_state: Dict[str, Any]
    dry_run: bool = True

class TrainRequest(BaseModel):
    X: List[List[float]]
    y: List[float]

class PredictRequest(BaseModel):
    features: List[float]


@app.get("/health")
def health():
    return {"status": "ok", "service": "profitpilotai"}


@app.post("/trade")
async def trade(req: TradeRequest, user=Depends(get_current_user)):
    """
    Evaluate strategy and execute if signal present. Requires auth dependency by default.
    """
    strategy = req.strategy
    if strategy not in default_strategy_manager.list_strategies():
        raise HTTPException(status_code=400, detail="Strategy not found")
    res = await evaluate_and_trade(strategy, req.market_state, dry_run=req.dry_run)
    # optionally log to supabase in supabase_utils (omitted here)
    return res


@app.post("/train")
def train(req: TrainRequest, user=Depends(get_current_user)):
    """
    Train incremental model on provided batch (X,y). Returns summary.
    """
    if not req.X or not req.y or len(req.X) != len(req.y):
        raise HTTPException(status_code=400, detail="Invalid training batch")
    train_on_batch(req.X, req.y)
    return {"status": "trained", "samples": len(req.X)}


@app.post("/predict")
def predict(req: PredictRequest, user=Depends(get_current_user)):
    """
    Predict a numeric score given feature vector.
    """
    if not req.features:
        raise HTTPException(status_code=400, detail="Empty features")
    try:
        score = predict_from_features(req.features)
        return {"score": float(score)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders")
def api_orders(user=Depends(get_current_user)):
    return {"orders": list_orders()}


@app.get("/portfolio")
def api_portfolio(user=Depends(get_current_user)):
    return {"portfolio": get_portfolio()}


@app.get("/strategies")
def api_strategies():
    return {"strategies": default_strategy_manager.list_strategies()}


if __name__ == "__main__":
    # for dev: run with `python backend/main.py`
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
