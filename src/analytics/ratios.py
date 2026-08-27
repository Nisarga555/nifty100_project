"""
Sprint 2 - Day 08 + Day 09
Financial Ratio Engine

Day 08:
    - Net Profit Margin
    - Operating Profit Margin
    - ROE
    - ROCE
    - ROA

Day 09:
    - Debt-to-Equity
    - High Leverage Flag
    - Interest Coverage Ratio
    - Debt Free ICR Label
    - ICR Warning Flag
    - Net Debt
    - Asset Turnover
"""

from typing import Optional


# =====================================================================
# COMMON HELPER
# =====================================================================

def _to_float(value) -> Optional[float]:
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number


# =====================================================================
# DAY 08 — PROFITABILITY RATIOS
# =====================================================================

def percentage_difference(
    reported: Optional[float],
    calculated: Optional[float],
) -> Optional[float]:
    """Return absolute difference between two percentage values."""

    reported = _to_float(reported)
    calculated = _to_float(calculated)

    if reported is None or calculated is None:
        return None

    return abs(reported - calculated)


def net_profit_margin(
    net_profit,
    sales,
) -> Optional[float]:
    """
    Net Profit Margin = net_profit / sales * 100

    Returns None when sales is zero or unavailable.
    """

    net_profit = _to_float(net_profit)
    sales = _to_float(sales)

    if net_profit is None or sales is None:
        return None

    if sales == 0:
        return None

    return (net_profit / sales) * 100


def operating_profit_margin(
    operating_profit,
    sales,
) -> Optional[float]:
    """
    Operating Profit Margin =
        operating_profit / sales * 100

    Returns None when sales is zero or unavailable.
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
    Calculate OPM and compare it with the source OPM.

    mismatch = True when difference > tolerance.
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


def return_on_equity(
    net_profit,
    equity_capital,
    reserves,
) -> Optional[float]:
    """
    ROE = net_profit /
          (equity_capital + reserves) * 100

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


def calculate_ebit(
    operating_profit,
    other_income,
) -> Optional[float]:
    """
    EBIT proxy:

        operating_profit + other_income
    """

    operating_profit = _to_float(operating_profit)
    other_income = _to_float(other_income)

    if operating_profit is None:
        return None

    if other_income is None:
        other_income = 0.0

    return operating_profit + other_income


def return_on_capital_employed(
    operating_profit,
    other_income,
    equity_capital,
    reserves,
    borrowings,
) -> Optional[float]:
    """
    ROCE = EBIT /
           (equity + reserves + borrowings) * 100
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


def roce_sector_classification(
    broad_sector,
    roce,
    sector_benchmark=None,
) -> Optional[str]:
    """
    Financial-sector ROCE uses a sector-relative benchmark.

    Financials:
        ROCE >= benchmark -> Above Sector Benchmark
        ROCE < benchmark  -> Below Sector Benchmark
        no benchmark      -> Benchmark Required

    Other sectors:
        Absolute Assessment
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


def return_on_assets(
    net_profit,
    total_assets,
) -> Optional[float]:
    """
    ROA = net_profit / total_assets * 100

    Returns None when total_assets == 0.
    """

    net_profit = _to_float(net_profit)
    total_assets = _to_float(total_assets)

    if net_profit is None or total_assets is None:
        return None

    if total_assets == 0:
        return None

    return (net_profit / total_assets) * 100


# =====================================================================
# DAY 09 — LEVERAGE & EFFICIENCY
# =====================================================================

def debt_to_equity(
    borrowings,
    equity_capital,
    reserves,
) -> Optional[float]:
    """
    Debt-to-Equity = borrowings / equity

    equity = equity_capital + reserves

    Rules:
        - borrowings == 0 -> 0
        - equity <= 0 -> None
        - missing required values -> None
    """

    borrowings = _to_float(borrowings)
    equity_capital = _to_float(equity_capital)
    reserves = _to_float(reserves)

    if (
        borrowings is None
        or equity_capital is None
        or reserves is None
    ):
        return None

    # Explicit Sprint 2 requirement:
    # debt-free companies return 0, not None.
    if borrowings == 0:
        return 0.0

    equity = equity_capital + reserves

    if equity <= 0:
        return None

    return borrowings / equity


def high_leverage_flag(
    debt_to_equity_value,
    broad_sector,
    threshold: float = 5.0,
) -> bool:
    """
    High leverage flag.

    D/E > 5 AND company is NOT in Financials -> True.

    Financial companies are excluded because structurally high leverage
    is normal for banks, NBFCs and insurers.
    """

    debt_to_equity_value = _to_float(
        debt_to_equity_value
    )

    if debt_to_equity_value is None:
        return False

    is_financials = (
        str(broad_sector).strip().lower()
        == "financials"
    )

    if is_financials:
        return False

    return debt_to_equity_value > threshold


def interest_coverage_ratio(
    operating_profit,
    other_income,
    interest,
) -> Optional[float]:
    """
    Interest Coverage Ratio =

        (operating_profit + other_income) / interest

    Returns None when interest == 0.

    A None result is interpreted as debt-free for the
    separate ICR label.
    """

    ebit = calculate_ebit(
        operating_profit,
        other_income,
    )

    interest = _to_float(interest)

    if ebit is None or interest is None:
        return None

    if interest == 0:
        return None

    return ebit / interest


def interest_coverage_label(
    interest_coverage,
) -> Optional[str]:
    """
    Convert ICR into the required display label.

    None -> Debt Free
    """

    if interest_coverage is None:
        return "Debt Free"

    return None


def interest_coverage_warning(
    interest_coverage,
    threshold: float = 1.5,
) -> bool:
    """
    ICR warning flag.

    True when ICR < 1.5.
    None / debt-free does not produce a warning.
    """

    interest_coverage = _to_float(
        interest_coverage
    )

    if interest_coverage is None:
        return False

    return interest_coverage < threshold


def net_debt(
    borrowings,
    investments,
) -> Optional[float]:
    """
    Net Debt = borrowings - investments

    Investments are used as the project's liquid-asset proxy.
    """

    borrowings = _to_float(borrowings)
    investments = _to_float(investments)

    if borrowings is None or investments is None:
        return None

    return borrowings - investments


def asset_turnover(
    sales,
    total_assets,
) -> Optional[float]:
    """
    Asset Turnover = sales / total_assets

    Returns None when total_assets == 0.
    """

    sales = _to_float(sales)
    total_assets = _to_float(total_assets)

    if sales is None or total_assets is None:
        return None

    if total_assets == 0:
        return None

    return sales / total_assets


# =====================================================================
# COMPLETE DAY 08 + DAY 09 CALCULATION
# =====================================================================

def calculate_profitability_ratios(row) -> dict:
    """
    Calculate Day 08 profitability ratios.
    """

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

    return {
        "net_profit_margin_pct": net_profit_margin(
            row.get("net_profit"),
            row.get("sales"),
        ),
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
        "return_on_assets_pct": return_on_assets(
            row.get("net_profit"),
            row.get("total_assets"),
        ),
    }


def calculate_leverage_efficiency_ratios(row) -> dict:
    """
    Calculate all Day 09 leverage and efficiency KPIs.
    """

    de = debt_to_equity(
        row.get("borrowings"),
        row.get("equity_capital"),
        row.get("reserves"),
    )

    icr = interest_coverage_ratio(
        row.get("operating_profit"),
        row.get("other_income"),
        row.get("interest"),
    )

    return {
        "debt_to_equity": de,

        "high_leverage_flag": high_leverage_flag(
            de,
            row.get("broad_sector"),
        ),

        "interest_coverage": icr,

        "icr_label": interest_coverage_label(
            icr,
        ),

        "icr_warning_flag": interest_coverage_warning(
            icr,
        ),

        "net_debt": net_debt(
            row.get("borrowings"),
            row.get("investments"),
        ),

        "asset_turnover": asset_turnover(
            row.get("sales"),
            row.get("total_assets"),
        ),
    }


def calculate_all_day08_day09_ratios(row) -> dict:
    """
    Calculate both Day 08 and Day 09 KPIs.

    This function will be useful when we connect the ratio engine
    to the SQLite financial_ratios table.
    """

    result = {}

    result.update(
        calculate_profitability_ratios(row)
    )

    result.update(
        calculate_leverage_efficiency_ratios(row)
    )

    return result