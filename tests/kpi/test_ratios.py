import pytest

from src.analytics.ratios import (
    net_profit_margin,
    operating_profit_margin,
    check_operating_profit_margin,
    return_on_equity,
    return_on_capital_employed,
    return_on_assets,
    roce_sector_classification,
    calculate_profitability_ratios,
    debt_to_equity,
    high_leverage_flag,
    interest_coverage_ratio,
    interest_coverage_label,
    interest_coverage_warning,
    net_debt,
    asset_turnover,
    calculate_leverage_efficiency_ratios,
    calculate_all_day08_day09_ratios,
)


# =====================================================================
# DAY 08 — NET PROFIT MARGIN
# =====================================================================

def test_net_profit_margin_normal():
    result = net_profit_margin(
        net_profit=200,
        sales=1000,
    )

    assert result == pytest.approx(20.0)


def test_net_profit_margin_zero_sales():
    result = net_profit_margin(
        net_profit=200,
        sales=0,
    )

    assert result is None


# =====================================================================
# DAY 08 — OPERATING PROFIT MARGIN
# =====================================================================

def test_operating_profit_margin_normal():
    result = operating_profit_margin(
        operating_profit=150,
        sales=1000,
    )

    assert result == pytest.approx(15.0)


def test_opm_cross_check_match():
    result = check_operating_profit_margin(
        operating_profit=150,
        sales=1000,
        reported_opm=15,
    )

    assert result["calculated_opm"] == pytest.approx(15.0)
    assert result["difference"] == pytest.approx(0.0)
    assert result["mismatch"] is False


def test_opm_cross_check_mismatch():
    result = check_operating_profit_margin(
        operating_profit=150,
        sales=1000,
        reported_opm=20,
    )

    assert result["calculated_opm"] == pytest.approx(15.0)
    assert result["difference"] == pytest.approx(5.0)
    assert result["mismatch"] is True


# =====================================================================
# DAY 08 — ROE
# =====================================================================

def test_roe_normal():
    result = return_on_equity(
        net_profit=200,
        equity_capital=100,
        reserves=900,
    )

    assert result == pytest.approx(20.0)


def test_roe_negative_equity_returns_none():
    result = return_on_equity(
        net_profit=200,
        equity_capital=100,
        reserves=-200,
    )

    assert result is None


# =====================================================================
# DAY 08 — ROCE
# =====================================================================

def test_roce_normal():
    result = return_on_capital_employed(
        operating_profit=200,
        other_income=20,
        equity_capital=100,
        reserves=400,
        borrowings=500,
    )

    assert result == pytest.approx(22.0)


# =====================================================================
# DAY 08 — ROA
# =====================================================================

def test_roa_zero_assets():
    result = return_on_assets(
        net_profit=100,
        total_assets=0,
    )

    assert result is None


# =====================================================================
# DAY 08 — FINANCIAL SECTOR ROCE
# =====================================================================

def test_financials_use_sector_benchmark():
    result = roce_sector_classification(
        broad_sector="Financials",
        roce=12.0,
        sector_benchmark=10.0,
    )

    assert result == "Above Sector Benchmark"


# =====================================================================
# DAY 08 — INTEGRATION
# =====================================================================

def test_calculate_profitability_ratios():
    row = {
        "sales": 1000,
        "net_profit": 200,
        "operating_profit": 150,
        "opm_percentage": 15,
        "equity_capital": 100,
        "reserves": 900,
        "other_income": 20,
        "borrowings": 500,
        "total_assets": 2000,
        "broad_sector": "Industrials",
    }

    result = calculate_profitability_ratios(row)

    assert result["net_profit_margin_pct"] == pytest.approx(20.0)

    assert result["operating_profit_margin_pct"] == pytest.approx(
        15.0
    )

    assert result["return_on_equity_pct"] == pytest.approx(
        20.0
    )

    assert result["return_on_capital_employed_pct"] == pytest.approx(
        11.3333333333
    )

    assert result["return_on_assets_pct"] == pytest.approx(
        10.0
    )

    assert result["opm_mismatch_flag"] is False


# =====================================================================
# DAY 09 — DEBT TO EQUITY
# =====================================================================

def test_debt_to_equity_normal():
    result = debt_to_equity(
        borrowings=500,
        equity_capital=100,
        reserves=900,
    )

    # 500 / (100 + 900) = 0.5
    assert result == pytest.approx(0.5)


def test_debt_to_equity_debt_free_returns_zero():
    result = debt_to_equity(
        borrowings=0,
        equity_capital=100,
        reserves=900,
    )

    assert result == pytest.approx(0.0)


def test_debt_to_equity_negative_equity_returns_none():
    result = debt_to_equity(
        borrowings=500,
        equity_capital=100,
        reserves=-200,
    )

    assert result is None


# =====================================================================
# DAY 09 — HIGH LEVERAGE FLAG
# =====================================================================

def test_high_debt_to_equity_flag():
    result = high_leverage_flag(
        debt_to_equity_value=6.0,
        broad_sector="Industrials",
    )

    assert result is True


def test_financials_high_debt_not_flagged():
    result = high_leverage_flag(
        debt_to_equity_value=10.0,
        broad_sector="Financials",
    )

    assert result is False


# =====================================================================
# DAY 09 — INTEREST COVERAGE
# =====================================================================

def test_interest_coverage_normal():
    result = interest_coverage_ratio(
        operating_profit=200,
        other_income=20,
        interest=110,
    )

    # (200 + 20) / 110 = 2
    assert result == pytest.approx(2.0)


def test_interest_coverage_zero_interest_returns_none():
    result = interest_coverage_ratio(
        operating_profit=200,
        other_income=20,
        interest=0,
    )

    assert result is None


def test_icr_label_debt_free():
    result = interest_coverage_label(None)

    assert result == "Debt Free"


def test_icr_warning_below_threshold():
    result = interest_coverage_warning(
        interest_coverage=1.2,
    )

    assert result is True


def test_icr_warning_above_threshold():
    result = interest_coverage_warning(
        interest_coverage=2.0,
    )

    assert result is False


# =====================================================================
# DAY 09 — NET DEBT
# =====================================================================

def test_net_debt():
    result = net_debt(
        borrowings=1000,
        investments=300,
    )

    assert result == pytest.approx(700.0)


# =====================================================================
# DAY 09 — ASSET TURNOVER
# =====================================================================

def test_asset_turnover_normal():
    result = asset_turnover(
        sales=2000,
        total_assets=1000,
    )

    assert result == pytest.approx(2.0)


def test_asset_turnover_zero_assets():
    result = asset_turnover(
        sales=2000,
        total_assets=0,
    )

    assert result is None


# =====================================================================
# DAY 09 — INTEGRATION
# =====================================================================

def test_calculate_leverage_efficiency_ratios():
    row = {
        "borrowings": 500,
        "equity_capital": 100,
        "reserves": 900,
        "operating_profit": 200,
        "other_income": 20,
        "interest": 110,
        "investments": 300,
        "sales": 2000,
        "total_assets": 1000,
        "broad_sector": "Industrials",
    }

    result = calculate_leverage_efficiency_ratios(row)

    assert result["debt_to_equity"] == pytest.approx(0.5)

    assert result["high_leverage_flag"] is False

    assert result["interest_coverage"] == pytest.approx(2.0)

    assert result["icr_label"] is None

    assert result["icr_warning_flag"] is False

    assert result["net_debt"] == pytest.approx(200.0)

    assert result["asset_turnover"] == pytest.approx(2.0)


def test_calculate_all_day08_day09_ratios():
    row = {
        "sales": 1000,
        "net_profit": 200,
        "operating_profit": 150,
        "opm_percentage": 15,
        "equity_capital": 100,
        "reserves": 900,
        "other_income": 20,
        "borrowings": 500,
        "interest": 85,
        "investments": 100,
        "total_assets": 2000,
        "broad_sector": "Industrials",
    }

    result = calculate_all_day08_day09_ratios(row)

    assert result["net_profit_margin_pct"] == pytest.approx(
        20.0
    )

    assert result["return_on_equity_pct"] == pytest.approx(
        20.0
    )

    assert result["debt_to_equity"] == pytest.approx(
        0.5
    )

    assert result["interest_coverage"] == pytest.approx(
        2.0
    )

    assert result["net_debt"] == pytest.approx(
        400.0
    )

    assert result["asset_turnover"] == pytest.approx(
        0.5
    )