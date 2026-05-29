"""xKDR cloud-bias correction algorithm (Python port).

Reference: Patnaik, Shah, Tayal, Thomas (2021)
"But clouds got in my way" — xKDR Working Paper 7.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .utils import CF_OBS_THRESHOLD


def correct_cloud_bias(
    df: pd.DataFrame,
    cf_threshold: int = CF_OBS_THRESHOLD,
    radiance_col: str = "radiance_raw",
    cf_col: str = "cf_obs",
    corrected_col: str = "radiance_corrected",
) -> pd.DataFrame:
    """Apply xKDR cloud-bias correction to a monthly radiance time-series.

    The core insight: when cloud-free observations drop (monsoon months),
    measured radiance is biased downward by -10% to -30%.

    Algorithm:
    1. Identify 'good' months (cf_obs >= cf_threshold).
    2. Fit OLS: radiance = alpha + beta * cf_obs on good months.
    3. For cloudy months, predict what radiance would be at median clear-sky cf_obs.
    4. Apply ratio correction: corrected = raw * (predicted_at_median / predicted_at_actual).
    5. Only correct upward (cloud bias is always downward).

    Args:
        df: DataFrame with at least radiance_col and cf_col columns.
        cf_threshold: Cloud-free observation threshold (default 8).
        radiance_col: Column name for raw radiance.
        cf_col: Column name for cloud-free observation count.
        corrected_col: Output column name for corrected radiance.

    Returns:
        DataFrame with new column corrected_col added.
    """
    df = df.copy()
    rad = df[radiance_col].values.astype(float)
    cf = df[cf_col].values.astype(float)

    good_mask = cf >= cf_threshold
    cloudy_mask = ~good_mask

    corrected = rad.copy()

    if good_mask.sum() >= 3:
        good_cf = cf[good_mask]
        good_rad = rad[good_mask]

        slope, intercept, r_value, p_value, std_err = stats.linregress(good_cf, good_rad)

        median_cf = float(np.median(good_cf))

        for i in np.where(cloudy_mask)[0]:
            if np.isnan(rad[i]) or cf[i] <= 0:
                continue
            predicted_at_actual = intercept + slope * cf[i]
            predicted_at_median = intercept + slope * median_cf

            if predicted_at_actual > 0 and predicted_at_median > predicted_at_actual:
                ratio = predicted_at_median / predicted_at_actual
                corrected[i] = rad[i] * ratio
    else:
        # Not enough good months — use seasonal median ratio as fallback
        corrected = _fallback_seasonal_correction(rad, cf, cf_threshold)

    # Never correct downward
    corrected = np.maximum(corrected, rad)

    # Propagate NaN
    corrected[np.isnan(rad)] = np.nan

    df[corrected_col] = corrected
    return df


def _fallback_seasonal_correction(
    rad: np.ndarray,
    cf: np.ndarray,
    cf_threshold: int,
) -> np.ndarray:
    """Fallback: scale cloudy months by the ratio of clear-sky median to cloudy median."""
    good_mask = cf >= cf_threshold
    cloudy_mask = ~good_mask
    corrected = rad.copy()

    if good_mask.sum() == 0:
        return corrected

    clear_median = float(np.nanmedian(rad[good_mask]))
    cloudy_median = float(np.nanmedian(rad[cloudy_mask])) if cloudy_mask.sum() > 0 else clear_median

    if cloudy_median > 0 and clear_median > cloudy_median:
        ratio = clear_median / cloudy_median
        corrected[cloudy_mask] = rad[cloudy_mask] * ratio

    return corrected


def correction_stats(df: pd.DataFrame, cf_threshold: int = CF_OBS_THRESHOLD) -> dict:
    """Compute summary statistics about how much correction was applied.

    Args:
        df: DataFrame after correction (must have radiance_raw, radiance_corrected, cf_obs).
        cf_threshold: Threshold used during correction.

    Returns:
        Dict with keys: n_corrected, mean_uplift_pct, max_uplift_pct, months_below_threshold.
    """
    cloudy = df[df["cf_obs"] < cf_threshold]
    if cloudy.empty:
        return {"n_corrected": 0, "mean_uplift_pct": 0.0, "max_uplift_pct": 0.0, "months_below_threshold": 0}

    uplift = (cloudy["radiance_corrected"] - cloudy["radiance_raw"]) / cloudy["radiance_raw"] * 100
    uplift = uplift.replace([np.inf, -np.inf], np.nan).dropna()

    return {
        "n_corrected": int((uplift > 0).sum()),
        "mean_uplift_pct": float(uplift[uplift > 0].mean()) if (uplift > 0).any() else 0.0,
        "max_uplift_pct": float(uplift.max()) if len(uplift) > 0 else 0.0,
        "months_below_threshold": len(cloudy),
    }
