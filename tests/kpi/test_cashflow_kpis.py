import pytest

from src.analytics.cashflow_kpis import (
    free_cash_flow,
    cfo_pat_ratio,
    classify_cfo_quality,
    calculate_cfo_quality_score,
    calculate_cfo_quality,
    capex_intensity,
    classify_capex_intensity,
    fcf_conversion_rate,
    capital_allocation_pattern,
    capital_allocation_record,
    calculate_cashflow_kpis,
)


# =====================================================================
# FREE CASH FLOW
# =====================================================================

def test_free_cash_flow():
    result = free_cash_flow(
        operating_activity=500,
        investing_activity=-200,
    )

    assert result == pytest.approx(300.0)


def test_negative_free_cash_flow_allowed():
    result = free_cash_flow(
        operating_activity=100,
        investing_activity=-250,
    )

    assert result == pytest.approx(-150.0)


# =====================================================================
# CFO / PAT
# =====================================================================

def test_cfo_pat_ratio():
    result = cfo_pat_ratio(
        cash_from_operations=300,
        net_profit=200,
    )

    assert result == pytest.approx(1.5)


def test_cfo_pat_zero_returns_none():
    result = cfo_pat_ratio(
        cash_from_operations=300,
        net_profit=0,
    )

    assert result is None


# =====================================================================
# CFO QUALITY
# =====================================================================

def test_cfo_quality_high():
    result = classify_cfo_quality(1.2)

    assert result == "High Quality"


def test_cfo_quality_moderate():
    result = classify_cfo_quality(0.75)

    assert result == "Moderate"


def test_cfo_quality_accrual_risk():
    result = classify_cfo_quality(0.4)

    assert result == "Accrual Risk"


def test_five_year_cfo_quality():
    cfo = [
        120,
        150,
        180,
        210,
        240,
    ]

    pat = [
        100,
        100,
        100,
        100,
        100,
    ]

    result = calculate_cfo_quality_score(
        cfo,
        pat,
    )

    assert result == pytest.approx(1.8)


def test_cfo_quality_result():
    result = calculate_cfo_quality(
        [120, 130, 140, 150, 160],
        [100, 100, 100, 100, 100],
    )

    assert result["cfo_quality_score"] == pytest.approx(
        1.4
    )

    assert result["cfo_quality_label"] == "High Quality"


# =====================================================================
# CAPEX INTENSITY
# =====================================================================

def test_capex_intensity():
    result = capex_intensity(
        investing_activity=-50,
        sales=1000,
    )

    assert result == pytest.approx(5.0)


def test_capex_asset_light():
    result = classify_capex_intensity(2.5)

    assert result == "Asset Light"


def test_capex_moderate():
    result = classify_capex_intensity(5.0)

    assert result == "Moderate"


def test_capex_capital_intensive():
    result = classify_capex_intensity(10.0)

    assert result == "Capital Intensive"


# =====================================================================
# FCF CONVERSION
# =====================================================================

def test_fcf_conversion():
    result = fcf_conversion_rate(
        free_cash_flow_value=300,
        operating_profit=200,
    )

    assert result == pytest.approx(150.0)


def test_fcf_conversion_zero_operating_profit():
    result = fcf_conversion_rate(
        free_cash_flow_value=300,
        operating_profit=0,
    )

    assert result is None


# =====================================================================
# CAPITAL ALLOCATION PATTERNS
# =====================================================================

def test_reinvestor_pattern():
    result = capital_allocation_pattern(
        operating_activity=500,
        investing_activity=-300,
        financing_activity=-100,
        cfo_pat_ratio_value=0.8,
    )

    assert result == "Reinvestor"


def test_shareholder_returns_pattern():
    result = capital_allocation_pattern(
        operating_activity=500,
        investing_activity=-300,
        financing_activity=-100,
        cfo_pat_ratio_value=1.5,
    )

    assert result == "Shareholder Returns"


def test_liquidating_assets_pattern():
    result = capital_allocation_pattern(
        operating_activity=500,
        investing_activity=200,
        financing_activity=-100,
    )

    assert result == "Liquidating Assets"


def test_distress_signal_pattern():
    result = capital_allocation_pattern(
        operating_activity=-500,
        investing_activity=200,
        financing_activity=300,
    )

    assert result == "Distress Signal"


def test_growth_funded_by_debt_pattern():
    result = capital_allocation_pattern(
        operating_activity=-500,
        investing_activity=-300,
        financing_activity=800,
    )

    assert result == "Growth Funded by Debt"


def test_cash_accumulator_pattern():
    result = capital_allocation_pattern(
        operating_activity=500,
        investing_activity=200,
        financing_activity=100,
    )

    assert result == "Cash Accumulator"


def test_pre_revenue_pattern():
    result = capital_allocation_pattern(
        operating_activity=-500,
        investing_activity=-300,
        financing_activity=-100,
    )

    assert result == "Pre-Revenue"


def test_mixed_pattern():
    result = capital_allocation_pattern(
        operating_activity=500,
        investing_activity=-300,
        financing_activity=200,
    )

    assert result == "Mixed"


# =====================================================================
# CAPITAL ALLOCATION RECORD
# =====================================================================

def test_capital_allocation_record():
    result = capital_allocation_record(
        company_id="ABB",
        year="2024-03",
        operating_activity=500,
        investing_activity=-300,
        financing_activity=-100,
        cfo_pat_ratio_value=0.8,
    )

    assert result == {
        "company_id": "ABB",
        "year": "2024-03",
        "cfo_sign": "+",
        "cfi_sign": "-",
        "cff_sign": "-",
        "pattern_label": "Reinvestor",
    }


# =====================================================================
# COMPLETE KPI CALCULATION
# =====================================================================

def test_calculate_cashflow_kpis():
    row = {
        "operating_activity": 500,
        "investing_activity": -200,
        "financing_activity": -100,
        "sales": 1000,
        "operating_profit": 250,
        "net_profit": 200,
    }

    result = calculate_cashflow_kpis(row)

    assert result["free_cash_flow"] == pytest.approx(
        300.0
    )

    assert result["cfo_pat_ratio"] == pytest.approx(
        2.5
    )

    assert result["capex_intensity_pct"] == pytest.approx(
        20.0
    )

    assert result["capex_intensity_label"] == (
        "Capital Intensive"
    )

    assert result["fcf_conversion_rate_pct"] == pytest.approx(
        120.0
    )

    assert result["cfo_sign"] == "+"
    assert result["cfi_sign"] == "-"
    assert result["cff_sign"] == "-"

    assert result["capital_allocation_pattern"] == (
        "Shareholder Returns"
    )