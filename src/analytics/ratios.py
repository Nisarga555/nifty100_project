"""
Sprint 2 - Day 08
Financial Ratio Engine

Profitability ratios:
    - Net Profit Margin
    - Operating Profit Margin
    - Return on Equity
    - Return on Capital Employed
    - Return on Assets

The functions are intentionally kept independent of pandas/SQLite so that
they can be unit-tested easily and later used by the full ratio engine.
"""

from typing import Optional


def _to_float(value) -> Optional[float]:
    """
    Safely convert a value to float.

    Returns None for missing/non-numeric values.
    """
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number


# ---------------------------------------------------------------------
# DQ / Ratio helper
# ---------------------------------------------------------------------

def percentage_difference(
    reported: Optional[float],
    calculated: Optional[float],
) -> Optional[float]:
    """
    Return absolute percentage-point difference between two percentages.

    Example:
        reported   = 20
        calculated = 21.2
        result     = 1.2
    """

    reported = _to_float(reported)
    calculated = _to_float(calculated)

    if reported is None or calculated is None:
        return None

    return abs(reported - calculated)


# ---------------------------------------------------------------------
# 1. Net Profit Margin
# ---------------------------------------------------------------------

def net_profit_margin(
    net_profit,
    sales,
) -> Optional[float]:
    """
    Net Profit Margin = net_profit / sales * 100

    Returns None when:
        - sales is missing
        - sales == 0
    """

    net_profit = _to_float(net_profit)
    sales = _to_float(sales)

    if net_profit is None or sales is None:
        return None

    if sales == 0:
        return None

    return (net_profit / sales) * 100


# ---------------------------------------------------------------------
# 2. Operating Profit Margin
# ---------------------------------------------------------------------

def operating_profit_margin(
    operating_profit,
    sales,
) -> Optional[float]:
    """
    Operating Profit Margin = operating_profit / sales * 100

    Returns None when:
        - sales is missing
        - sales == 0
        - operating_profit is missing
    """

    operating_profit = _to_float(operating_profit)
    sales = _to_float(sales)

    if operating_profit is None or sales is None:
        return None

    if sales == 0:
        return None

    return (operating_profit / sales) * 100


def check_operating_profit_margin(
    operating_profit,
    sales,
    reported_opm,
    tolerance: float = 1.0,
) -> dict:
    """
    Calculate OPM and cross-check it against the source OPM.

    Returns:

        {
            "calculated_opm": ...,
            "reported_opm": ...,
            "difference": ...,
            "mismatch": True/False
        }

    A mismatch is recorded when the difference is > 1 percentage point.
    """

    calculated = operating_profit_margin(
        operating_profit,
        sales,
    )

    reported = _to_float(reported_opm)

    if calculated is None or reported is None:
        return {
            "calculated_opm": calculated,
            "reported_opm": reported,
            "difference": None,
            "mismatch": False,
        }

    difference = abs(calculated - reported)

    return {
        "calculated_opm": calculated,
        "reported_opm": reported,
        "difference": difference,
        "mismatch": difference > tolerance,
    }


# ---------------------------------------------------------------------
# 3. Return on Equity
# ---------------------------------------------------------------------

def return_on_equity(
    net_profit,
    equity_capital,
    reserves,
) -> Optional[float]:
    """
    Return on Equity =

        net_profit
        ------------------------------- * 100
        equity_capital + reserves

    Returns None when total equity <= 0.
    """

    net_profit = _to_float(net_profit)
    equity_capital = _to_float(equity_capital)
    reserves = _to_float(reserves)

    if (
        net_profit is None
        or equity_capital is None
        or reserves is None
    ):
        return None

    equity = equity_capital + reserves

    if equity <= 0:
        return None

    return (net_profit / equity) * 100


# ---------------------------------------------------------------------
# 4. EBIT
# ---------------------------------------------------------------------

def calculate_ebit(
    operating_profit,
    other_income,
) -> Optional[float]:
    """
    EBIT proxy used by this project:

        EBIT = operating_profit + other_income

    This follows the project's source-data structure where interest is
    separately reported.
    """

    operating_profit = _to_float(operating_profit)
    other_income = _to_float(other_income)

    if operating_profit is None:
        return None

    if other_income is None:
        other_income = 0.0

    return operating_profit + other_income


# ---------------------------------------------------------------------
# 5. Return on Capital Employed
# ---------------------------------------------------------------------

def return_on_capital_employed(
    operating_profit,
    other_income,
    equity_capital,
    reserves,
    borrowings,
) -> Optional[float]:
    """
    Return on Capital Employed =

        EBIT
        --------------------------------------------- * 100
        equity_capital + reserves + borrowings

    EBIT is calculated as:

        operating_profit + other_income

    Returns None when capital employed <= 0.
    """

    ebit = calculate_ebit(
        operating_profit,
        other_income,
    )

    equity_capital = _to_float(equity_capital)
    reserves = _to_float(reserves)
    borrowings = _to_float(borrowings)

    if (
        ebit is None
        or equity_capital is None
        or reserves is None
        or borrowings is None
    ):
        return None

    capital_employed = (
        equity_capital
        + reserves
        + borrowings
    )

    if capital_employed <= 0:
        return None

    return (ebit / capital_employed) * 100


# ---------------------------------------------------------------------
# 6. Financial-sector ROCE treatment
# ---------------------------------------------------------------------

def roce_sector_classification(
    broad_sector,
    roce,
    sector_benchmark=None,
) -> Optional[str]:
    """
    Classify ROCE using a sector-relative benchmark for Financials.

    The Sprint 2 specification requires Financials to use a
    sector-relative benchmark rather than an absolute threshold.

    Therefore:

        Financials + benchmark available:
            ROCE >= benchmark -> "Above Sector Benchmark"
            ROCE < benchmark  -> "Below Sector Benchmark"

        Financials + no benchmark:
            "Benchmark Required"

        Other sectors:
            "Absolute Assessment"

    This helper deliberately does not invent an absolute ROCE threshold.
    The benchmark will be supplied by the broader analytics/screener layer.
    """

    roce = _to_float(roce)
    sector_benchmark = _to_float(sector_benchmark)

    if roce is None:
        return None

    if str(broad_sector).strip().lower() == "financials":

        if sector_benchmark is None:
            return "Benchmark Required"

        if roce >= sector_benchmark:
            return "Above Sector Benchmark"

        return "Below Sector Benchmark"

    return "Absolute Assessment"


# ---------------------------------------------------------------------
# 7. Return on Assets
# ---------------------------------------------------------------------

def return_on_assets(
    net_profit,
    total_assets,
) -> Optional[float]:
    """
    Return on Assets = net_profit / total_assets * 100

    Returns None when total_assets == 0.
    """

    net_profit = _to_float(net_profit)
    total_assets = _to_float(total_assets)

    if net_profit is None or total_assets is None:
        return None

    if total_assets == 0:
        return None

    return (net_profit / total_assets) * 100


# ---------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------

def calculate_profitability_ratios(row) -> dict:
    """
    Calculate all Day 08 profitability ratios for a pandas Series,
    dictionary, or dictionary-like object.

    Expected fields:

        sales
        net_profit
        operating_profit
        opm_percentage
        equity_capital
        reserves
        other_income
        borrowings
        total_assets
        broad_sector

    Missing optional fields are handled safely.
    """

    npl = net_profit_margin(
        row.get("net_profit"),
        row.get("sales"),
    )

    opm_check = check_operating_profit_margin(
        row.get("operating_profit"),
        row.get("sales"),
        row.get("opm_percentage"),
    )

    roe = return_on_equity(
        row.get("net_profit"),
        row.get("equity_capital"),
        row.get("reserves"),
    )

    roce = return_on_capital_employed(
        row.get("operating_profit"),
        row.get("other_income"),
        row.get("equity_capital"),
        row.get("reserves"),
        row.get("borrowings"),
    )

    roa = return_on_assets(
        row.get("net_profit"),
        row.get("total_assets"),
    )

    return {
        "net_profit_margin_pct": npl,
        "operating_profit_margin_pct": opm_check[
            "calculated_opm"
        ],
        "reported_opm_percentage": opm_check[
            "reported_opm"
        ],
        "opm_difference_pct_points": opm_check[
            "difference"
        ],
        "opm_mismatch_flag": opm_check[
            "mismatch"
        ],
        "return_on_equity_pct": roe,
        "return_on_capital_employed_pct": roce,
        "return_on_assets_pct": roa,
    }