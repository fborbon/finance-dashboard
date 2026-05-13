import numpy as np
import pandas as pd

TRANSFER_CATS = {"own transfer", "transfer"}
LOOKBACK_MONTHS = 24
MIN_MONTHS = 2
TREND_MIN = 4


def predict_next_month(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    Predict income and expenses by category for the next calendar month.

    Returns {"income": {cat: €}, "expenses": {cat: €}} where expense values
    are positive (absolute spend). Uses a linear trend when ≥ TREND_MIN monthly
    data points exist per category, otherwise falls back to the category mean.
    The current (partial) month and transfer categories are excluded from training.
    """
    current_month = pd.Timestamp.now().to_period("M").to_timestamp()
    hist = df[
        ~df["category"].isin(TRANSFER_CATS)
        & (df["date"] < current_month)
    ].copy()

    if hist.empty:
        return {"income": {}, "expenses": {}}

    hist["month"] = hist["date"].dt.to_period("M").dt.to_timestamp()

    cutoff = hist["month"].max() - pd.DateOffset(months=LOOKBACK_MONTHS - 1)
    hist = hist[hist["month"] >= cutoff]

    monthly = hist.groupby(["month", "category"])["amount"].sum().reset_index()

    income_preds: dict[str, float] = {}
    expense_preds: dict[str, float] = {}

    for cat, grp in monthly.groupby("category"):
        grp = grp.sort_values("month")
        pos = grp.loc[grp["amount"] > 0, "amount"].values
        neg = grp.loc[grp["amount"] < 0, "amount"].abs().values

        if len(pos) >= MIN_MONTHS:
            income_preds[cat] = _extrapolate(pos)
        if len(neg) >= MIN_MONTHS:
            expense_preds[cat] = _extrapolate(neg)

    return {"income": income_preds, "expenses": expense_preds}


def _extrapolate(values: np.ndarray) -> float:
    """Linear-trend extrapolation for ≥ TREND_MIN points, mean otherwise."""
    if len(values) >= TREND_MIN:
        x = np.arange(len(values), dtype=float)
        slope, intercept = np.polyfit(x, values, 1)
        pred = slope * len(values) + intercept
    else:
        pred = float(values.mean())
    return max(0.0, round(float(pred), 2))
