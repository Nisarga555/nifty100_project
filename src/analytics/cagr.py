"""
CAGR and Growth Analytics

Supports:
- Revenue CAGR
- PAT CAGR
- EPS CAGR
- 3Y / 5Y / 10Y CAGR
- CAGR classification flags
- Mar 2019 / Sep 2024 / Dec 2020 year formats
- Row-level endpoint-aware CAGR
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


# =====================================================================
# FLAGS
# =====================================================================

NORMAL = "NORMAL"
DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
TURNAROUND = "TURNAROUND"
BOTH_NEGATIVE = "BOTH_NEGATIVE"
ZERO_BASE = "ZERO_BASE"
INSUFFICIENT = "INSUFFICIENT"

DEFAULT_WINDOWS = (3, 5, 10)


# =====================================================================
# BASIC HELPERS
# =====================================================================

def _to_float(value: Any) -> Optional[float]:
    """Safely convert value to float."""

    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(result):
        return None

    return result


def parse_year(year: Any) -> Optional[int]:
    """
    Extract a four-digit year.

    Examples:
        2019
        "2019"
        "Mar 2019"
        "Sep 2024"
        "2020-03"
    """

    if year is None:
        return None

    text = str(year).strip()

    match = re.search(r"(19|20)\d{2}", text)

    if match:
        return int(match.group(0))

    try:
        number = float(text)

        if 1900 <= number <= 2100:
            return int(number)

    except (TypeError, ValueError):
        pass

    return None


# =====================================================================
# CAGR VALUE HELPER
# =====================================================================

def cagr_value(
    start_value: Any,
    end_value: Any,
    years: int,
) -> Optional[float]:
    """
    Calculate the mathematical CAGR value.

    Returns None when:
    - values are missing
    - years <= 0
    - start <= 0
    - end <= 0
    """

    start = _to_float(start_value)
    end = _to_float(end_value)

    if start is None or end is None:
        return None

    if years <= 0:
        return None

    if start <= 0 or end <= 0:
        return None

    try:
        return ((end / start) ** (1.0 / years) - 1.0) * 100.0

    except (ValueError, ZeroDivisionError, OverflowError):
        return None


# =====================================================================
# CAGR FLAG HELPER
# =====================================================================

def cagr_flag(
    start_value: Any,
    end_value: Any,
    years: Optional[int] = None,
) -> str:
    """
    Classify CAGR behaviour.

    'years' is accepted for backward compatibility with the
    existing test suite. It does not affect classification.

    Rules:
        positive -> positive = NORMAL
        positive -> negative = DECLINE_TO_LOSS
        negative -> positive = TURNAROUND
        negative -> negative = BOTH_NEGATIVE
        zero start = ZERO_BASE
        missing = INSUFFICIENT
    """

    start = _to_float(start_value)
    end = _to_float(end_value)

    if start is None or end is None:
        return INSUFFICIENT

    if start == 0:
        return ZERO_BASE

    if start > 0 and end > 0:
        return NORMAL

    if start > 0 and end < 0:
        return DECLINE_TO_LOSS

    if start < 0 and end > 0:
        return TURNAROUND

    if start < 0 and end < 0:
        return BOTH_NEGATIVE

    # End value exactly zero.
    if start > 0 and end == 0:
        return DECLINE_TO_LOSS

    if start < 0 and end == 0:
        return TURNAROUND

    return INSUFFICIENT


# =====================================================================
# FULL CAGR RESULT
# =====================================================================

def calculate_cagr(
    start_value: Any,
    end_value: Any,
    years: int,
) -> Dict[str, Any]:
    """
    Calculate CAGR and return both value and classification.

    Returns:

        {
            "value": 10.0,
            "flag": "NORMAL"
        }
    """

    flag = cagr_flag(
        start_value,
        end_value,
        years=years,
    )

    # Insufficient / special cases should have no CAGR value.
    if flag != NORMAL:
        return {
            "value": None,
            "flag": flag,
        }

    value = cagr_value(
        start_value,
        end_value,
        years,
    )

    if value is None:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    return {
        "value": value,
        "flag": NORMAL,
    }


# =====================================================================
# WINDOW CAGR
# =====================================================================

def calculate_window_cagr(
    values_by_year: Mapping[Any, Any],
    window: int,
    end_year: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Calculate CAGR for a specific historical window.

    IMPORTANT:

    If end_year is supplied, the CAGR ends at that year.

    Example:

        end_year = 2020

    means a 5-year CAGR uses:

        2015 -> 2020

    rather than automatically using the latest available year.
    """

    if not values_by_year:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    cleaned: Dict[int, float] = {}

    for year, value in values_by_year.items():

        year_int = parse_year(year)
        value_float = _to_float(value)

        if year_int is None or value_float is None:
            continue

        cleaned[year_int] = value_float

    if not cleaned:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    # ---------------------------------------------------------------
    # Endpoint
    # ---------------------------------------------------------------

    if end_year is None:
        actual_end_year = max(cleaned.keys())

    else:
        actual_end_year = parse_year(end_year)

        if actual_end_year is None:
            return {
                "value": None,
                "flag": INSUFFICIENT,
            }

    # ---------------------------------------------------------------
    # Endpoint must exist
    # ---------------------------------------------------------------

    if actual_end_year not in cleaned:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    # ---------------------------------------------------------------
    # Start year
    # ---------------------------------------------------------------

    start_year = actual_end_year - window

    if start_year not in cleaned:
        return {
            "value": None,
            "flag": INSUFFICIENT,
        }

    start_value = cleaned[start_year]
    end_value = cleaned[actual_end_year]

    return calculate_cagr(
        start_value=start_value,
        end_value=end_value,
        years=window,
    )


# =====================================================================
# MULTI-WINDOW CAGR
# =====================================================================

def calculate_multi_window_cagr(
    values_by_year: Mapping[Any, Any],
    windows: Sequence[int] = DEFAULT_WINDOWS,
    end_year: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Calculate multiple CAGR windows.

    Returns:

        cagr_3yr
        cagr_3yr_flag
        cagr_5yr
        cagr_5yr_flag
        cagr_10yr
        cagr_10yr_flag
    """

    result: Dict[str, Any] = {}

    for window in windows:

        calculation = calculate_window_cagr(
            values_by_year,
            window,
            end_year=end_year,
        )

        result[f"cagr_{window}yr"] = calculation["value"]
        result[f"cagr_{window}yr_flag"] = calculation["flag"]

    return result


# =====================================================================
# HISTORY CONVERSION
# =====================================================================

def _history_to_year_dictionaries(
    history: Sequence[Any],
) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    Dict[str, Any],
]:
    """
    Convert historical rows into Revenue / PAT / EPS dictionaries.

    Dictionary format supported:

        {
            "year": "Sep 2020",
            "sales": 1000,
            "net_profit": 100,
            "eps": 10
        }

    Tuple/list format supported:

        ("Sep 2020", 1000, 100, 10)
    """

    revenue_by_year: Dict[str, Any] = {}
    pat_by_year: Dict[str, Any] = {}
    eps_by_year: Dict[str, Any] = {}

    for row in history:

        year = None
        revenue = None
        pat = None
        eps = None

        # -----------------------------------------------------------
        # Dictionary row
        # -----------------------------------------------------------

        if isinstance(row, Mapping):

            year = (
                row.get("year")
                or row.get("Year")
                or row.get("date")
                or row.get("Date")
            )

            if "sales" in row:
                revenue = row.get("sales")
            else:
                revenue = row.get("revenue")

            if "net_profit" in row:
                pat = row.get("net_profit")
            else:
                pat = row.get("pat")

            eps = row.get("eps")

        # -----------------------------------------------------------
        # List / tuple row
        # -----------------------------------------------------------

        elif isinstance(row, (list, tuple)):

            if len(row) >= 1:
                year = row[0]

            if len(row) >= 2:
                revenue = row[1]

            if len(row) >= 3:
                pat = row[2]

            if len(row) >= 4:
                eps = row[3]

        if year is None:
            continue

        year_text = str(year)

        revenue_by_year[year_text] = revenue
        pat_by_year[year_text] = pat
        eps_by_year[year_text] = eps

    return (
        revenue_by_year,
        pat_by_year,
        eps_by_year,
    )


# =====================================================================
# GROWTH METRICS
# =====================================================================

def calculate_growth_metrics(
    revenue_by_year: Any,
    pat_by_year: Any = None,
    eps_by_year: Any = None,
    end_year: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Calculate Revenue / PAT / EPS CAGR.

    Includes both values and flags.

    Example:

        revenue_cagr_5yr
        revenue_cagr_5yr_flag

    When end_year is provided, all calculations use that year
    as their endpoint.
    """

    # ---------------------------------------------------------------
    # History supplied as list / tuple
    # ---------------------------------------------------------------

    if isinstance(revenue_by_year, (list, tuple)):

        (
            revenue_history,
            pat_history,
            eps_history,
        ) = _history_to_year_dictionaries(
            revenue_by_year
        )

        revenue_by_year = revenue_history

        if pat_by_year is None:
            pat_by_year = pat_history

        if eps_by_year is None:
            eps_by_year = eps_history

    # ---------------------------------------------------------------
    # Empty histories
    # ---------------------------------------------------------------

    if revenue_by_year is None:
        revenue_by_year = {}

    if pat_by_year is None:
        pat_by_year = {}

    if eps_by_year is None:
        eps_by_year = {}

    # ---------------------------------------------------------------
    # Revenue
    # ---------------------------------------------------------------

    revenue_metrics = calculate_multi_window_cagr(
        revenue_by_year,
        windows=DEFAULT_WINDOWS,
        end_year=end_year,
    )

    # ---------------------------------------------------------------
    # PAT
    # ---------------------------------------------------------------

    pat_metrics = calculate_multi_window_cagr(
        pat_by_year,
        windows=DEFAULT_WINDOWS,
        end_year=end_year,
    )

    # ---------------------------------------------------------------
    # EPS
    # ---------------------------------------------------------------

    eps_metrics = calculate_multi_window_cagr(
        eps_by_year,
        windows=DEFAULT_WINDOWS,
        end_year=end_year,
    )

    result: Dict[str, Any] = {}

    # ---------------------------------------------------------------
    # Revenue output
    # ---------------------------------------------------------------

    for window in DEFAULT_WINDOWS:

        result[f"revenue_cagr_{window}yr"] = (
            revenue_metrics[f"cagr_{window}yr"]
        )

        result[f"revenue_cagr_{window}yr_flag"] = (
            revenue_metrics[f"cagr_{window}yr_flag"]
        )

    # ---------------------------------------------------------------
    # PAT output
    # ---------------------------------------------------------------

    for window in DEFAULT_WINDOWS:

        result[f"pat_cagr_{window}yr"] = (
            pat_metrics[f"cagr_{window}yr"]
        )

        result[f"pat_cagr_{window}yr_flag"] = (
            pat_metrics[f"cagr_{window}yr_flag"]
        )

    # ---------------------------------------------------------------
    # EPS output
    # ---------------------------------------------------------------

    for window in DEFAULT_WINDOWS:

        result[f"eps_cagr_{window}yr"] = (
            eps_metrics[f"cagr_{window}yr"]
        )

        result[f"eps_cagr_{window}yr_flag"] = (
            eps_metrics[f"cagr_{window}yr_flag"]
        )

    return result


# =====================================================================
# SAFE WRAPPER
# =====================================================================

def calculate_growth_safely(
    history: Sequence[Any],
    end_year: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Safe wrapper used by the population script.
    """

    empty_result: Dict[str, Any] = {}

    for metric in (
        "revenue",
        "pat",
        "eps",
    ):
        for window in DEFAULT_WINDOWS:
            empty_result[f"{metric}_cagr_{window}yr"] = None
            empty_result[f"{metric}_cagr_{window}yr_flag"] = (
                INSUFFICIENT
            )

    if not history:
        return empty_result

    try:

        return calculate_growth_metrics(
            history,
            end_year=end_year,
        )

    except Exception:

        return empty_result


# =====================================================================
# EXPORTS
# =====================================================================

__all__ = [
    "NORMAL",
    "DECLINE_TO_LOSS",
    "TURNAROUND",
    "BOTH_NEGATIVE",
    "ZERO_BASE",
    "INSUFFICIENT",
    "calculate_cagr",
    "cagr_value",
    "cagr_flag",
    "calculate_window_cagr",
    "calculate_multi_window_cagr",
    "calculate_growth_metrics",
    "calculate_growth_safely",
    "parse_year",
]