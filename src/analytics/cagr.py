"""
Sprint 2 - Day 10
CAGR Engine

Handles:
    - Revenue CAGR
    - PAT CAGR
    - EPS CAGR
    - 3-year, 5-year and 10-year periods
    - Six required CAGR edge cases
"""

from typing import Optional


# =====================================================================
# CAGR FLAGS
# =====================================================================

NORMAL = "NORMAL"
DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
TURNAROUND = "TURNAROUND"
BOTH_NEGATIVE = "BOTH_NEGATIVE"
ZERO_BASE = "ZERO_BASE"
INSUFFICIENT = "INSUFFICIENT"


# =====================================================================
# BASIC CAGR
# =====================================================================

def calculate_cagr(
    start_value,
    end_value,
    years,
) -> dict:
    """
    Calculate CAGR with all six required edge cases.

    Formula:

        CAGR = ((end / start) ** (1 / n) - 1) * 100

    Returns:
        {
            "value": CAGR percentage or None,
            "flag": status flag
        }
    """

    if start_value is None or end_value is None:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    if years is None:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    try:
        start = float(start_value)
        end = float(end_value)
        n = int(years)
    except (TypeError, ValueError):
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    if n <= 0:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    # Zero base cannot be used in CAGR formula.
    if start == 0:
        return {
            "value": None,
            "flag": ZERO_BASE,
        }

    # Positive -> Positive
    if start > 0 and end > 0:
        value = (
            ((end / start) ** (1 / n)) - 1
        ) * 100

        return {
            "value": value,
            "flag": NORMAL,
        }

    # Positive -> Negative
    if start > 0 and end < 0:
        return {
            "value": None,
            "flag": DECLINE_TO_LOSS,
        }

    # Negative -> Positive
    if start < 0 and end > 0:
        return {
            "value": None,
            "flag": TURNAROUND,
        }

    # Negative -> Negative
    if start < 0 and end < 0:
        return {
            "value": None,
            "flag": BOTH_NEGATIVE,
        }

    # Any remaining case, including end == 0.
    #
    # A positive/negative starting point reaching exactly zero
    # cannot produce a meaningful CAGR percentage.
    return {
        "value": None,
        "flag": ZERO_BASE,
    }


# =====================================================================
# SIMPLE CAGR VALUE HELPER
# =====================================================================

def cagr_value(
    start_value,
    end_value,
    years,
) -> Optional[float]:
    """
    Return only the CAGR percentage.

    Edge cases return None.
    """

    result = calculate_cagr(
        start_value,
        end_value,
        years,
    )

    return result["value"]


# =====================================================================
# CAGR FLAG HELPER
# =====================================================================

def cagr_flag(
    start_value,
    end_value,
    years,
) -> str:
    """
    Return only the CAGR status flag.
    """

    result = calculate_cagr(
        start_value,
        end_value,
        years,
    )

    return result["flag"]


# =====================================================================
# YEAR WINDOW VALIDATION
# =====================================================================

def has_sufficient_years(
    available_years,
    required_years,
) -> bool:
    """
    Check whether enough observations are available
    for a requested CAGR window.

    For a 5-year CAGR we need the beginning and ending
    observations separated by at least 5 years.
    """

    if available_years is None:
        return False

    try:
        years = sorted(
            {
                int(float(year))
                for year in available_years
                if year is not None
            }
        )
    except (TypeError, ValueError):
        return False

    if not years:
        return False

    return (
        max(years) - min(years)
        >= int(required_years)
    )


# =====================================================================
# DATAFRAME / SERIES CAGR
# =====================================================================

def calculate_window_cagr(
    values_by_year,
    window,
) -> dict:
    """
    Calculate CAGR from a year -> value mapping.

    Example:

        {
            2019: 100,
            2020: 110,
            2021: 125,
            2022: 140,
            2023: 160,
            2024: 180
        }

    For window=5:
        start = 2019
        end   = 2024

    Returns:
        {
            "value": ...,
            "flag": ...
        }
    """

    if not values_by_year:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    cleaned = {}

    for year, value in values_by_year.items():

        if year is None or value is None:
            continue

        try:
            year_int = int(float(year))
            value_float = float(value)
        except (TypeError, ValueError):
            continue

        cleaned[year_int] = value_float

    if not cleaned:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    required_window = int(window)

    end_year = max(cleaned.keys())
    start_year = end_year - required_window

    if start_year not in cleaned:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    return calculate_cagr(
        cleaned[start_year],
        cleaned[end_year],
        required_window,
    )


# =====================================================================
# MULTI-WINDOW CAGR
# =====================================================================

def calculate_multi_window_cagr(
    values_by_year,
    windows=(3, 5, 10),
) -> dict:
    """
    Calculate CAGR for multiple windows.

    Returns keys such as:

        cagr_3yr
        cagr_3yr_flag
        cagr_5yr
        cagr_5yr_flag
        cagr_10yr
        cagr_10yr_flag
    """

    result = {}

    for window in windows:

        cagr_result = calculate_window_cagr(
            values_by_year,
            window,
        )

        result[f"cagr_{window}yr"] = (
            cagr_result["value"]
        )

        result[f"cagr_{window}yr_flag"] = (
            cagr_result["flag"]
        )

    return result


# =====================================================================
# FINANCIAL GROWTH METRICS
# =====================================================================

def calculate_growth_metrics(
    revenue_by_year,
    pat_by_year,
    eps_by_year,
) -> dict:
    """
    Calculate Revenue, PAT and EPS CAGR for:

        - 3 years
        - 5 years
        - 10 years

    Each CAGR has a separate flag column.
    """

    result = {}

    revenue = calculate_multi_window_cagr(
        revenue_by_year
    )

    pat = calculate_multi_window_cagr(
        pat_by_year
    )

    eps = calculate_multi_window_cagr(
        eps_by_year
    )

    for window in (3, 5, 10):

        result[
            f"revenue_cagr_{window}yr"
        ] = revenue[f"cagr_{window}yr"]

        result[
            f"revenue_cagr_{window}yr_flag"
        ] = revenue[f"cagr_{window}yr_flag"]

        result[
            f"pat_cagr_{window}yr"
        ] = pat[f"cagr_{window}yr"]

        result[
            f"pat_cagr_{window}yr_flag"
        ] = pat[f"cagr_{window}yr_flag"]

        result[
            f"eps_cagr_{window}yr"
        ] = eps[f"cagr_{window}yr"]

        result[
            f"eps_cagr_{window}yr_flag"
        ] = eps[f"cagr_{window}yr_flag"]

    return result