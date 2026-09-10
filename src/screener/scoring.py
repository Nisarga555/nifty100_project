"""
NIFTY 100 - Sprint 3 Day 17
Composite Quality Scoring Engine

Scoring:
Profitability = 35%
    ROE  = 15%
    ROCE = 10%
    NPM  = 10%

Cash Quality = 30%
    FCF CAGR = 15%
    CFO/PAT  = 10%
    FCF positive = 5%

Growth = 20%
    Revenue CAGR 5Y = 10%
    PAT CAGR 5Y     = 10%

Leverage = 15%
    D/E = 10%
    ICR = 5%

Each metric is winsorised at P10/P90 and normalized to 0-100.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# METRIC CONFIGURATION
# ============================================================

METRIC_WEIGHTS = {
    "return_on_equity_pct": 15.0,
    "roce_pct": 10.0,
    "net_profit_margin_pct": 10.0,

    "fcf_cagr_5yr": 15.0,
    "cfo_pat_ratio": 10.0,
    "fcf_positive_score": 5.0,

    "revenue_cagr_5yr": 10.0,
    "pat_cagr_5yr": 10.0,

    "de_score": 10.0,
    "icr_score": 5.0,
}


# Metrics where HIGHER is better.
HIGHER_IS_BETTER = {
    "return_on_equity_pct",
    "roce_pct",
    "net_profit_margin_pct",
    "fcf_cagr_5yr",
    "cfo_pat_ratio",
    "fcf_positive_score",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "icr_score",
}


# ============================================================
# NUMERIC HELPERS
# ============================================================

def numeric_series(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:

    if column not in dataframe.columns:
        return pd.Series(
            np.nan,
            index=dataframe.index,
            dtype=float,
        )

    return pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )


def winsorize_series(
    series: pd.Series,
) -> pd.Series:
    """
    Winsorise a metric at P10 and P90.
    """

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    valid = numeric.dropna()

    if valid.empty:
        return numeric

    lower = valid.quantile(0.10)
    upper = valid.quantile(0.90)

    if pd.isna(lower) or pd.isna(upper):
        return numeric

    if lower == upper:
        return numeric

    return numeric.clip(
        lower=lower,
        upper=upper,
    )


def normalize_series(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """
    Winsorise at P10/P90 and normalize to 0-100.
    """

    winsorized = winsorize_series(series)

    valid = winsorized.dropna()

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float,
    )

    if valid.empty:
        return result

    lower = valid.min()
    upper = valid.max()

    if upper == lower:
        result.loc[valid.index] = 50.0
        return result

    if higher_is_better:
        normalized = (
            (winsorized - lower)
            / (upper - lower)
        ) * 100.0
    else:
        normalized = (
            (upper - winsorized)
            / (upper - lower)
        ) * 100.0

    return normalized.clip(
        lower=0,
        upper=100,
    )


# ============================================================
# SPECIAL METRIC CALCULATIONS
# ============================================================

def calculate_net_profit_margin(
    dataframe: pd.DataFrame,
) -> pd.Series:

    if "net_profit_margin_pct" in dataframe.columns:
        existing = numeric_series(
            dataframe,
            "net_profit_margin_pct",
        )

        if existing.notna().any():
            return existing

    net_profit = numeric_series(
        dataframe,
        "net_profit",
    )

    sales = numeric_series(
        dataframe,
        "sales",
    )

    result = pd.Series(
        np.nan,
        index=dataframe.index,
        dtype=float,
    )

    valid = sales.ne(0) & sales.notna()

    result.loc[valid] = (
        net_profit.loc[valid]
        / sales.loc[valid]
        * 100.0
    )

    return result


def calculate_cfo_pat_ratio(
    dataframe: pd.DataFrame,
) -> pd.Series:

    if "cfo_pat_ratio" in dataframe.columns:
        existing = numeric_series(
            dataframe,
            "cfo_pat_ratio",
        )

        if existing.notna().any():
            return existing

    cfo = numeric_series(
        dataframe,
        "cash_from_operations_cr",
    )

    pat = numeric_series(
        dataframe,
        "net_profit",
    )

    result = pd.Series(
        np.nan,
        index=dataframe.index,
        dtype=float,
    )

    valid = pat.ne(0) & pat.notna()

    result.loc[valid] = (
        cfo.loc[valid]
        / pat.loc[valid]
    )

    return result


def calculate_fcf_positive_score(
    dataframe: pd.DataFrame,
) -> pd.Series:

    fcf = numeric_series(
        dataframe,
        "free_cash_flow_cr",
    )

    return fcf.gt(0).astype(float) * 100.0


def calculate_de_score(
    dataframe: pd.DataFrame,
) -> pd.Series:

    de = numeric_series(
        dataframe,
        "debt_to_equity",
    )

    # Lower D/E is better.
    return normalize_series(
        de,
        higher_is_better=False,
    )


def calculate_icr_score(
    dataframe: pd.DataFrame,
) -> pd.Series:

    icr = numeric_series(
        dataframe,
        "interest_coverage",
    )

    if "icr_label" in dataframe.columns:

        debt_free = (
            dataframe["icr_label"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("debt free")
        )

        icr = icr.copy()

        # Debt-free companies receive the maximum ICR score.
        icr.loc[debt_free] = np.inf

    finite = icr.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    score = normalize_series(
        finite,
        higher_is_better=True,
    )

    if np.isinf(icr).any():
        score.loc[np.isinf(icr)] = 100.0

    return score


def get_metric_series(
    dataframe: pd.DataFrame,
    metric: str,
) -> pd.Series:

    if metric == "net_profit_margin_pct":
        return calculate_net_profit_margin(
            dataframe
        )

    if metric == "cfo_pat_ratio":
        return calculate_cfo_pat_ratio(
            dataframe
        )

    if metric == "fcf_positive_score":
        return calculate_fcf_positive_score(
            dataframe
        )

    if metric == "de_score":
        return numeric_series(
            dataframe,
            "debt_to_equity",
        )

    if metric == "icr_score":
        return numeric_series(
            dataframe,
            "interest_coverage",
        )

    return numeric_series(
        dataframe,
        metric,
    )


# ============================================================
# SECTOR RELATIVE NORMALIZATION
# ============================================================

def sector_relative_normalize(
    dataframe: pd.DataFrame,
    metric: str,
) -> pd.Series:
    """
    Normalize each metric within broad_sector.

    P10/P90 winsorisation is calculated separately
    for each sector.
    """

    values = get_metric_series(
        dataframe,
        metric,
    )

    result = pd.Series(
        np.nan,
        index=dataframe.index,
        dtype=float,
    )

    if "broad_sector" not in dataframe.columns:
        return normalize_series(
            values,
            higher_is_better=metric
            in HIGHER_IS_BETTER,
        )

    sectors = (
        dataframe["broad_sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    for sector_name in sectors.unique():

        mask = sectors.eq(sector_name)

        sector_values = values.loc[mask]

        normalized = normalize_series(
            sector_values,
            higher_is_better=metric
            in HIGHER_IS_BETTER,
        )

        result.loc[mask] = normalized

    return result


# ============================================================
# COMPOSITE SCORE
# ============================================================

def calculate_composite_quality_score(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add all component scores and final composite_quality_score.

    Final score is 0-100.
    """

    result = dataframe.copy()

    weighted_scores = []

    for metric, weight in METRIC_WEIGHTS.items():

        score = sector_relative_normalize(
            result,
            metric,
        )

        column_name = (
            f"{metric}_score"
        )

        result[column_name] = score

        weighted = (
            score
            * (weight / 100.0)
        )

        weighted_scores.append(
            weighted
        )

    if weighted_scores:

        score_frame = pd.concat(
            weighted_scores,
            axis=1,
        )

        result[
            "composite_quality_score"
        ] = score_frame.sum(
            axis=1,
            min_count=1,
        )

    else:

        result[
            "composite_quality_score"
        ] = np.nan

    result[
        "composite_quality_score"
    ] = result[
        "composite_quality_score"
    ].clip(
        lower=0,
        upper=100,
    )

    return result


# ============================================================
# PUBLIC ALIAS
# ============================================================

def add_composite_quality_score(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    return calculate_composite_quality_score(
        dataframe
    )