"""Bridge-regression nowcasting: predict a slow (quarterly) target from faster indicators."""
import numpy as np
import pandas as pd

from app.forecasting.result import ForecastResult


def bridge_nowcast(
    target: pd.Series, indicators: dict[str, pd.Series], use_pca: bool | None = None
) -> ForecastResult:
    import statsmodels.api as sm

    quarterly = pd.DataFrame(
        {name: series.resample("QS").mean() for name, series in indicators.items()}
    )
    names = list(indicators.keys())
    use_pca = use_pca if use_pca is not None else len(names) >= 4

    if use_pca:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        filled = quarterly.ffill().dropna()
        factors = PCA(n_components=min(2, len(names))).fit_transform(
            StandardScaler().fit_transform(filled)
        )
        X_all = pd.DataFrame(
            factors, index=filled.index,
            columns=[f"factor_{i + 1}" for i in range(factors.shape[1])],
        )
        method = "dynamic factor (PCA) bridge"
    else:
        X_all = quarterly
        method = "bridge regression (OLS)"

    aligned = X_all.join(target.rename("__target__"), how="left")
    train = aligned.dropna()
    if len(train) < 8:
        raise ValueError(
            f"Not enough overlapping quarters ({len(train)}) between target and indicators"
        )
    X_train = sm.add_constant(train.drop(columns="__target__"))
    fit = sm.OLS(train["__target__"], X_train).fit()

    # Nowcast quarters where indicators exist but the target isn't published yet
    future = aligned[aligned["__target__"].isna()].drop(columns="__target__").dropna()
    if future.empty:
        future = aligned.drop(columns="__target__").iloc[[-1]].dropna()
    X_future = sm.add_constant(future, has_constant="add")
    prediction = fit.get_prediction(X_future)
    frame95 = prediction.summary_frame(alpha=0.05)
    frame80 = prediction.summary_frame(alpha=0.2)

    return ForecastResult(
        model_name="Bridge nowcast",
        forecast_dates=[d.strftime("%Y-%m-%d") for d in future.index],
        point=[float(v) for v in frame95["mean"]],
        lower_80=[float(v) for v in frame80["obs_ci_lower"]],
        upper_80=[float(v) for v in frame80["obs_ci_upper"]],
        lower_95=[float(v) for v in frame95["obs_ci_lower"]],
        upper_95=[float(v) for v in frame95["obs_ci_upper"]],
        fitted=[float(v) for v in fit.fittedvalues],
        metadata={
            "method": method,
            "indicators": names,
            "r_squared": float(fit.rsquared),
            "coefficients": {k: float(v) for k, v in fit.params.items()},
            "n_train_quarters": len(train),
        },
        backtest={
            "in_sample_rmse": float(np.sqrt(np.mean(fit.resid**2))),
            "r_squared": float(fit.rsquared),
        },
    )
