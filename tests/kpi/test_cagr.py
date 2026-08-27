import pytest

from src.analytics.cagr import (
    NORMAL,
    DECLINE_TO_LOSS,
    TURNAROUND,
    BOTH_NEGATIVE,
    ZERO_BASE,
    INSUFFICIENT,
    calculate_cagr,
    cagr_value,
    cagr_flag,
    calculate_window_cagr,
    calculate_multi_window_cagr,
    calculate_growth_metrics,
)


# =====================================================================
# NORMAL CAGR
# =====================================================================

def test_normal_cagr():
    result = calculate_cagr(
        start_value=100,
        end_value=121,
        years=2,
    )

    assert result["value"] == pytest.approx(10.0)
    assert result["flag"] == NORMAL


# =====================================================================
# ZERO BASE
# =====================================================================

def test_zero_base():
    result = calculate_cagr(
        start_value=0,
        end_value=100,
        years=5,
    )

    assert result["value"] is None
    assert result["flag"] == ZERO_BASE


# =====================================================================
# POSITIVE TO NEGATIVE
# =====================================================================

def test_decline_to_loss():
    result = calculate_cagr(
        start_value=100,
        end_value=-50,
        years=5,
    )

    assert result["value"] is None
    assert result["flag"] == DECLINE_TO_LOSS


# =====================================================================
# NEGATIVE TO POSITIVE
# =====================================================================

def test_turnaround():
    result = calculate_cagr(
        start_value=-100,
        end_value=150,
        years=5,
    )

    assert result["value"] is None
    assert result["flag"] == TURNAROUND


# =====================================================================
# NEGATIVE TO NEGATIVE
# =====================================================================

def test_both_negative():
    result = calculate_cagr(
        start_value=-100,
        end_value=-150,
        years=5,
    )

    assert result["value"] is None
    assert result["flag"] == BOTH_NEGATIVE


# =====================================================================
# INSUFFICIENT DATA
# =====================================================================

def test_insufficient_years():
    result = calculate_window_cagr(
        {
            2022: 100,
            2023: 110,
            2024: 120,
        },
        window=5,
    )

    assert result["value"] is None
    assert result["flag"] == INSUFFICIENT


# =====================================================================
# CAGR VALUE HELPER
# =====================================================================

def test_cagr_value():
    result = cagr_value(
        start_value=100,
        end_value=133.1,
        years=3,
    )

    assert result == pytest.approx(10.0)


# =====================================================================
# CAGR FLAG HELPER
# =====================================================================

def test_cagr_flag():
    result = cagr_flag(
        start_value=100,
        end_value=-20,
        years=3,
    )

    assert result == DECLINE_TO_LOSS


# =====================================================================
# WINDOW CAGR
# =====================================================================

def test_window_cagr():
    result = calculate_window_cagr(
        {
            2019: 100,
            2020: 110,
            2021: 121,
            2022: 133.1,
            2023: 146.41,
            2024: 161.051,
        },
        window=5,
    )

    assert result["value"] == pytest.approx(10.0)
    assert result["flag"] == NORMAL


# =====================================================================
# MULTI-WINDOW CAGR
# =====================================================================

def test_multi_window_cagr():
    values = {
        2014: 100,
        2015: 110,
        2016: 121,
        2017: 133.1,
        2018: 146.41,
        2019: 161.051,
        2020: 177.1561,
        2021: 194.87171,
        2022: 214.358881,
        2023: 235.7947691,
        2024: 259.37424601,
    }

    result = calculate_multi_window_cagr(
        values,
        windows=(3, 5, 10),
    )

    assert result["cagr_3yr"] == pytest.approx(10.0)
    assert result["cagr_5yr"] == pytest.approx(10.0)
    assert result["cagr_10yr"] == pytest.approx(10.0)

    assert result["cagr_3yr_flag"] == NORMAL
    assert result["cagr_5yr_flag"] == NORMAL
    assert result["cagr_10yr_flag"] == NORMAL


# =====================================================================
# REVENUE / PAT / EPS GROWTH METRICS
# =====================================================================

def test_growth_metrics():
    revenue = {
        2019: 100,
        2020: 110,
        2021: 121,
        2022: 133.1,
        2023: 146.41,
        2024: 161.051,
    }

    pat = {
        2019: 50,
        2020: 55,
        2021: 60.5,
        2022: 66.55,
        2023: 73.205,
        2024: 80.5255,
    }

    eps = {
        2019: 10,
        2020: 11,
        2021: 12.1,
        2022: 13.31,
        2023: 14.641,
        2024: 16.1051,
    }

    result = calculate_growth_metrics(
        revenue_by_year=revenue,
        pat_by_year=pat,
        eps_by_year=eps,
    )

    assert result["revenue_cagr_5yr"] == pytest.approx(
        10.0
    )

    assert result["pat_cagr_5yr"] == pytest.approx(
        10.0,
        abs=0.01,
    )

    assert result["eps_cagr_5yr"] == pytest.approx(
        10.0,
        abs=0.01,
    )

    assert result["revenue_cagr_5yr_flag"] == NORMAL
    assert result["pat_cagr_5yr_flag"] == NORMAL
    assert result["eps_cagr_5yr_flag"] == NORMAL


# =====================================================================
# NEGATIVE / TURNAROUND GROWTH DATA
# =====================================================================

def test_growth_metrics_edge_cases():
    revenue = {
        2019: 100,
        2020: 120,
        2021: 140,
        2022: 160,
        2023: 180,
        2024: -20,
    }

    pat = {
        2019: -100,
        2020: -80,
        2021: -60,
        2022: -40,
        2023: -20,
        2024: 30,
    }

    eps = {
        2019: 0,
        2020: 2,
        2021: 4,
        2022: 6,
        2023: 8,
        2024: 10,
    }

    result = calculate_growth_metrics(
        revenue_by_year=revenue,
        pat_by_year=pat,
        eps_by_year=eps,
    )

    assert result["revenue_cagr_5yr"] is None
    assert result["revenue_cagr_5yr_flag"] == DECLINE_TO_LOSS

    assert result["pat_cagr_5yr"] is None
    assert result["pat_cagr_5yr_flag"] == TURNAROUND

    assert result["eps_cagr_5yr"] is None
    assert result["eps_cagr_5yr_flag"] == ZERO_BASE