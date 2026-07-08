"""
Lightweight univariate LSTM forecaster used as the "alt model" alongside
Prophet. Kept in its own module because TensorFlow is a heavy/optional
dependency - if it isn't installed, forecasting_service falls back to
Prophet/regression automatically instead of hard failing.
"""
from __future__ import annotations
import numpy as np

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models
    TF_AVAILABLE = True
except Exception:  # pragma: no cover - environment without TF
    TF_AVAILABLE = False


WINDOW = 24  # look back 24 steps to predict the next one


def _make_windows(series: np.ndarray, window: int = WINDOW):
    X, y = [], []
    for i in range(len(series) - window):
        X.append(series[i:i + window])
        y.append(series[i + window])
    return np.array(X), np.array(y)


class LSTMForecaster:
    """Simple stacked-LSTM next-step forecaster trained on a normalized series."""

    def __init__(self, window: int = WINDOW):
        self.window = window
        self.model = None
        self.min_ = 0.0
        self.max_ = 1.0

    def _scale(self, arr: np.ndarray) -> np.ndarray:
        span = (self.max_ - self.min_) or 1.0
        return (arr - self.min_) / span

    def _unscale(self, arr: np.ndarray) -> np.ndarray:
        span = (self.max_ - self.min_) or 1.0
        return arr * span + self.min_

    def fit(self, series: np.ndarray, epochs: int = 25):
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow not available in this environment")
        if len(series) < self.window + 5:
            raise ValueError("Not enough data points to train an LSTM (need at least window+5)")

        self.min_, self.max_ = float(series.min()), float(series.max())
        scaled = self._scale(series.astype("float32"))
        X, y = _make_windows(scaled, self.window)
        X = X.reshape((X.shape[0], X.shape[1], 1))

        self.model = models.Sequential([
            layers.Input(shape=(self.window, 1)),
            layers.LSTM(32, return_sequences=True),
            layers.LSTM(16),
            layers.Dense(8, activation="relu"),
            layers.Dense(1),
        ])
        self.model.compile(optimizer="adam", loss="mse")
        self.model.fit(X, y, epochs=epochs, batch_size=16, verbose=0)
        self._last_window = scaled[-self.window:]
        return self

    def forecast(self, steps: int) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Call fit() before forecast()")
        window = self._last_window.copy()
        preds = []
        for _ in range(steps):
            x = window.reshape((1, self.window, 1))
            next_val = self.model.predict(x, verbose=0)[0, 0]
            preds.append(next_val)
            window = np.append(window[1:], next_val)
        return self._unscale(np.array(preds))
