"""Nelson-Siegel yield curve fitting and factor-based extrapolation."""
import numpy as np


def nelson_siegel_curve(maturities, beta0: float, beta1: float, beta2: float, tau: float):
    m = np.asarray(maturities, dtype=float)
    x = m / tau
    loading = (1 - np.exp(-x)) / x
    return beta0 + beta1 * loading + beta2 * (loading - np.exp(-x))


def nelson_siegel_fit(maturities, yields) -> dict:
    """Grid over tau; betas by linear least squares per tau; best SSE wins."""
    m = np.asarray(maturities, dtype=float)
    y = np.asarray(yields, dtype=float)
    best = None
    for tau in np.linspace(0.2, 8.0, 60):
        x = m / tau
        loading = (1 - np.exp(-x)) / x
        design = np.column_stack([np.ones_like(m), loading, loading - np.exp(-x)])
        betas, *_ = np.linalg.lstsq(design, y, rcond=None)
        sse = float(np.sum((design @ betas - y) ** 2))
        if best is None or sse < best[0]:
            best = (sse, betas, tau)
    _, betas, tau = best
    return {
        "beta0": float(betas[0]),
        "beta1": float(betas[1]),
        "beta2": float(betas[2]),
        "tau": float(tau),
    }


def fit_curve_history(curves: dict[str, dict[float, float]]) -> dict:
    """Fit NS factors for each dated curve snapshot: {date: {maturity: yield}}."""
    factors = {}
    for date, curve in sorted(curves.items()):
        maturities = sorted(curve)
        params = nelson_siegel_fit(maturities, [curve[m] for m in maturities])
        factors[date] = params
    return factors
