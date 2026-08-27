"""
Sprint 2 - Day 11
Cash Flow KPIs & Capital Allocation

Implements:
    - Free Cash Flow
    - CFO Quality Score
    - CapEx Intensity
    - FCF Conversion Rate
    - Capital Allocation Pattern Classification
"""

from typing import Optional


# =====================================================================
# HELPERS
# =====================================================================

def _to_float(value) -> Optional[float]:
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# =====================================================================
# FREE CASH FLOW
# =====================================================================

def free_cash_flow(
    operating_activity,
    investing_activity,
) -> Optional[float]:
    """
    Free Cash Flow = CFO + CFI

    Negative FCF is valid and is therefore not converted to None.
    """

    cfo = _to_float(operating_activity)
    cfi = _to_float(investing_activity)

    if cfo is None or cfi is None:
        return None

    return cfo + cfi


# =====================================================================
# CFO / PAT
# =====================================================================

def cfo_pat_ratio(
    cash_from_operations,
    net_profit,
) -> Optional[float]:
    """
    CFO / PAT ratio.

    Returns None when PAT is zero or unavailable.
    """

    cfo = _to_float(cash_from_operations)
    pat = _to_float(net_profit)

    if cfo is None or pat is None:
        return None

    if pat == 0:
        return None

    return cfo / pat


# =====================================================================
# CFO QUALITY CLASSIFICATION
# =====================================================================

def classify_cfo_quality(
    cfo_pat_average,
) -> Optional[str]:
    """
    Classify average CFO/PAT ratio.

    > 1.0      -> High Quality
    0.5 - 1.0  -> Moderate
    < 0.5      -> Accrual Risk
    """

    value = _to_float(cfo_pat_average)

    if value is None:
        return None

    if value > 1.0:
        return "High Quality"

    if value >= 0.5:
        return "Moderate"

    return "Accrual Risk"


# =====================================================================
# FIVE-YEAR CFO QUALITY
# =====================================================================

def calculate_cfo_quality_score(
    cfo_values,
    pat_values,
) -> Optional[float]:
    """
    Calculate the average CFO/PAT ratio over up to five years.

    Only years where PAT != 0 and both values are available
    are included in the average.

    The function expects the values to already represent the
    relevant five-year window.
    """

    if cfo_values is None or pat_values is None:
        return None

    ratios = []

    for cfo, pat in zip(cfo_values, pat_values):

        ratio = cfo_pat_ratio(
            cfo,
            pat,
        )

        if ratio is not None:
            ratios.append(ratio)

    if not ratios:
        return None

    return sum(ratios) / len(ratios)


def calculate_cfo_quality(
    cfo_values,
    pat_values,
) -> dict:
    """
    Return both the five-year CFO quality score
    and its classification.
    """

    score = calculate_cfo_quality_score(
        cfo_values,
        pat_values,
    )

    return {
        "cfo_quality_score": score,
        "cfo_quality_label": classify_cfo_quality(score),
    }


# =====================================================================
# CAPEX INTENSITY
# =====================================================================

def capex_intensity(
    investing_activity,
    sales,
) -> Optional[float]:
    """
    CapEx Intensity = abs(CFI) / sales * 100

    Thresholds:
        < 3%      -> Asset Light
        3% - 8%    -> Moderate
        > 8%       -> Capital Intensive
    """

    cfi = _to_float(investing_activity)
    sales = _to_float(sales)

    if cfi is None or sales is None:
        return None

    if sales == 0:
        return None

    return (abs(cfi) / sales) * 100


def classify_capex_intensity(
    intensity,
) -> Optional[str]:
    """
    Classify CapEx intensity.
    """

    intensity = _to_float(intensity)

    if intensity is None:
        return None

    if intensity < 3:
        return "Asset Light"

    if intensity <= 8:
        return "Moderate"

    return "Capital Intensive"


# =====================================================================
# FCF CONVERSION
# =====================================================================

def fcf_conversion_rate(
    free_cash_flow_value,
    operating_profit,
) -> Optional[float]:
    """
    FCF Conversion Rate = FCF / Operating Profit * 100

    Returns None when operating profit is zero.
    """

    fcf = _to_float(free_cash_flow_value)
    op = _to_float(operating_profit)

    if fcf is None or op is None:
        return None

    if op == 0:
        return None

    return (fcf / op) * 100


# =====================================================================
# CAPITAL ALLOCATION PATTERNS
# =====================================================================

def _sign(value) -> str:
    """
    Convert a cash-flow value into:
        +  positive
        -  negative
        0  zero
    """

    value = _to_float(value)

    if value is None:
        return "0"

    if value > 0:
        return "+"

    if value < 0:
        return "-"

    return "0"


def capital_allocation_pattern(
    operating_activity,
    investing_activity,
    financing_activity,
    cfo_pat_ratio_value=None,
) -> str:
    """
    Classify capital allocation based on
    CFO / CFI / CFF signs.

    Patterns:

        (+,-,-) -> Reinvestor
        (+,-,-) with high CFO/PAT -> Shareholder Returns
        (+,+,-) -> Liquidating Assets
        (-,+,+) -> Distress Signal
        (-,-,+) -> Growth Funded by Debt
        (+,+,+) -> Cash Accumulator
        (-,-,-) -> Pre-Revenue
        (+,-,+) -> Mixed

    High CFO/PAT is defined as > 1.0.

    The high-quality (+,-,-) case is checked before
    the normal Reinvestor classification.
    """

    cfo_sign = _sign(operating_activity)
    cfi_sign = _sign(investing_activity)
    cff_sign = _sign(financing_activity)

    pattern = (
        cfo_sign,
        cfi_sign,
        cff_sign,
    )

    high_quality = False

    ratio = _to_float(
        cfo_pat_ratio_value
    )

    if ratio is not None:
        high_quality = ratio > 1.0

    # ---------------------------------------------------------------
    # Required 8 patterns
    # ---------------------------------------------------------------

    if pattern == ("+", "-", "-"):

        if high_quality:
            return "Shareholder Returns"

        return "Reinvestor"

    if pattern == ("+", "+", "-"):
        return "Liquidating Assets"

    if pattern == ("-", "+", "+"):
        return "Distress Signal"

    if pattern == ("-", "-", "+"):
        return "Growth Funded by Debt"

    if pattern == ("+", "+", "+"):
        return "Cash Accumulator"

    if pattern == ("-", "-", "-"):
        return "Pre-Revenue"

    if pattern == ("+", "-", "+"):
        return "Mixed"

    # This also handles combinations containing zero.
    return "Mixed"


# =====================================================================
# SIGN OUTPUT
# =====================================================================

def capital_allocation_record(
    company_id,
    year,
    operating_activity,
    investing_activity,
    financing_activity,
    cfo_pat_ratio_value=None,
) -> dict:
    """
    Create the required capital allocation output record.
    """

    return {
        "company_id": company_id,
        "year": year,
        "cfo_sign": _sign(operating_activity),
        "cfi_sign": _sign(investing_activity),
        "cff_sign": _sign(financing_activity),
        "pattern_label": capital_allocation_pattern(
            operating_activity,
            investing_activity,
            financing_activity,
            cfo_pat_ratio_value,
        ),
    }


# =====================================================================
# COMPLETE CASH-FLOW KPI CALCULATION
# =====================================================================

def calculate_cashflow_kpis(row) -> dict:
    """
    Calculate all single-year cash-flow KPIs.
    """

    cfo = row.get("operating_activity")
    cfi = row.get("investing_activity")
    cff = row.get("financing_activity")

    fcf = free_cash_flow(
        cfo,
        cfi,
    )

    capex = capex_intensity(
        cfi,
        row.get("sales"),
    )

    conversion = fcf_conversion_rate(
        fcf,
        row.get("operating_profit"),
    )

    cfo_pat = cfo_pat_ratio(
        cfo,
        row.get("net_profit"),
    )

    return {
        "free_cash_flow": fcf,

        "cfo_pat_ratio": cfo_pat,

        "capex_intensity_pct": capex,

        "capex_intensity_label": classify_capex_intensity(
            capex
        ),

        "fcf_conversion_rate_pct": conversion,

        "cfo_sign": _sign(cfo),

        "cfi_sign": _sign(cfi),

        "cff_sign": _sign(cff),

        "capital_allocation_pattern": capital_allocation_pattern(
            cfo,
            cfi,
            cff,
            cfo_pat,
        ),
    }