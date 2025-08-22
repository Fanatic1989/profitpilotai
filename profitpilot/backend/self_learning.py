"""
backend/self_learning.py

A minimal incremental learning module using scikit-learn's SGDRegressor for
online updates (partial_fit). This is a supervised / regression-style learner,
intended as a lightweight 'self-learning' starter:

- model predicts a numeric 'signal_score' (higher -> more likely to buy)
- You provide features + a target label when calling /train
- Model persists to disk via joblib

Notes:
- This is not RL. It's a supervised incremental learner (Option A).
- You must collect labeled data (or synthetic reward labels) to train it.
"""

import os
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.linear_model import SGDRegressor
from sklearn.preprocessing import StandardScaler
import joblib

MODEL_DIR = os.getenv("MODEL_DIR", "./models")
MODEL_PATH = os.path.join(MODEL_DIR, "sgd_regressor.joblib")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.joblib")

DEFAULT_FEATURE_COUNT = 8

# Ensure models directory exists
os.makedirs(MODEL_DIR, exist_ok=True)


class IncrementalLearner:
    def __init__(self, n_features: int = DEFAULT_FEATURE_COUNT):
        self.n_features = n_features
        self.model: Optional[SGDRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        self._init_or_load()

    def _init_or_load(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                data = joblib.load(MODEL_PATH)
                self.model = data
                self.scaler = joblib.load(SCALER_PATH)
                return
            except Exception:
                # continue to initialize fresh
                pass
        # initialize fresh
        self.model = SGDRegressor(max_iter=1000, tol=1e-3)
        # scaler requires partial fit interface: use StandardScaler with mean/var online
        self.scaler = StandardScaler()
        # For first partial_fit we need to call with a sample and provide y
        # We'll leave initialization to first train call.

    def save(self):
        if self.model is not None:
            joblib.dump(self.model, MODEL_PATH)
        if self.scaler is not None:
            joblib.dump(self.scaler, SCALER_PATH)

    def predict(self, features: List[float]) -> float:
        import numpy as np
        if self.model is None or self.scaler is None:
            raise RuntimeError("Model not initialized")
        x = np.array(features).reshape(1, -1)
        x_scaled = self.scaler.transform(x)
        pred = float(self.model.predict(x_scaled)[0])
        return pred

    def partial_train(self, X: List[List[float]], y: List[float]):
        """
        X: list of feature lists (each length n_features or will be padded/truncated)
        y: list of numeric targets
        """
        import numpy as np
        Xarr = np.array([self._pad_or_truncate(x) for x in X], dtype=float)
        yarr = np.array(y, dtype=float)
        # fit scaler incrementally
        if not hasattr(self.scaler, "mean_") or getattr(self.scaler, "mean_", None) is None:
            # first call: fit
            self.scaler.fit(Xarr)
        else:
            # partial update: StandardScaler doesn't have partial_fit, so we approximate by refit on concatenation
            # For production use, use a scaler with partial_fit or compute running mean/var manually.
            self.scaler.partial_fit(Xarr) if hasattr(self.scaler, "partial_fit") else self.scaler.fit(Xarr)

        Xs = self.scaler.transform(Xarr)
        # Partial fit model
        if not hasattr(self.model, "coef_") or getattr(self.model, "coef_", None) is None:
            # initial partial_fit must include classes in some estimators, but SGDRegressor doesn't need classes
            self.model.partial_fit(Xs, yarr)
        else:
            self.model.partial_fit(Xs, yarr)
        # save after training for persistence
        self.save()

    def _pad_or_truncate(self, arr: List[float]) -> List[float]:
        # ensure fixed width
        out = list(arr[: self.n_features])
        if len(out) < self.n_features:
            out = out + [0.0] * (self.n_features - len(out))
        return out


# Expose a default learner instance
_default_learner = IncrementalLearner(n_features=DEFAULT_FEATURE_COUNT)


def train_on_batch(X: List[List[float]], y: List[float]):
    """
    Convenience wrapper to train the default learner on a batch.
    """
    _default_learner.partial_train(X, y)


def predict_from_features(features: List[float]) -> float:
    return _default_learner.predict(features)
