"""
backend/routes/api.py

API router for strategy/trade/self-learning endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List

from ..strategy_service import default_strategy_manager
from ..trading_service import evaluate_and_trade, list_orders, get_portfolio
from ..self_learning import train_on_batch, predict_from_features
from ..auth_utils import get_current_user

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "profitpilotai"}


@router.get("/strategies")
def strategies():
    return {"strategies": default_strategy_manager.list_strategies()}


class TradePayload:
    strategy: str
    market_state: Dict[str, Any]
    dry_run: bool = True


@router.post("/trade")
async def trade(payload: Dict[str, Any], user=Depends(get_current_user)):
    strategy = payload.get("strategy")
    market_state = payload.get("market_state", {})
    dry_run = payload.get("dry_run", True)
    if strategy not in default_strategy_manager.list_strategies():
        raise HTTPException(status_code=400, detail="Strategy not found")
    res = await evaluate_and_trade(strategy, market_state, dry_run=dry_run)
    return res


@router.get("/orders")
def orders(user=Depends(get_current_user)):
    return {"orders": list_orders()}


@router.get("/portfolio")
def portfolio(user=Depends(get_current_user)):
    return {"portfolio": get_portfolio()}


@router.post("/train")
def train(payload: Dict[str, Any], user=Depends(get_current_user)):
    X = payload.get("X")
    y = payload.get("y")
    if not X or not y or len(X) != len(y):
        raise HTTPException(status_code=400, detail="Invalid training data")
    train_on_batch(X, y)
    return {"status": "trained", "samples": len(X)}


@router.post("/predict")
def predict(payload: Dict[str, Any], user=Depends(get_current_user)):
    features = payload.get("features")
    if not features:
        raise HTTPException(status_code=400, detail="No features provided")
    try:
        score = predict_from_features(features)
        return {"score": float(score)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
