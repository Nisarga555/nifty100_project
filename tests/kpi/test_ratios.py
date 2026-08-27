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
)


# =====================================================================
# NET PROFIT MARGIN
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
# OPERATING PROFIT MARGIN
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
# RETURN ON EQUITY
# =====================================================================

def test_roe_normal():
    result = return_on_equity(
        net_profit=200,
        equity_capital=100,
        reserves=900,
    )

    # Equity = 100 + 900 = 1000
    # ROE = 200 / 1000 * 100 = 20%
    assert result == pytest.approx(20.0)


def test_roe_negative_equity_returns_none():
    result = return_on_equity(
        net_profit=200,
        equity_capital=100,
        reserves=-200,
    )

    # Equity = 100 - 200 = -100
    # Negative equity -> None
    assert result is None


# =====================================================================
# RETURN ON CAPITAL EMPLOYED
# =====================================================================

def test_roce_normal():
    result = return_on_capital_employed(
        operating_profit=200,
        other_income=20,
        equity_capital=100,
        reserves=400,
        borrowings=500,
    )

    # EBIT = operating profit + other income
    # EBIT = 200 + 20 = 220
    #
    # Capital employed =
    # equity capital + reserves + borrowings
    # = 100 + 400 + 500
    # = 1000
    #
    # ROCE = 220 / 1000 * 100
    # = 22%
    assert result == pytest.approx(22.0)


# =====================================================================
# RETURN ON ASSETS
# =====================================================================

def test_roa_zero_assets():
    result = return_on_assets(
        net_profit=100,
        total_assets=0,
    )

    assert result is None


# =====================================================================
# FINANCIAL-SECTOR ROCE
# =====================================================================

def test_financials_use_sector_benchmark():
    result = roce_sector_classification(
        broad_sector="Financials",
        roce=12.0,
        sector_benchmark=10.0,
    )

    assert result == "Above Sector Benchmark"


# =====================================================================
# INTEGRATION-STYLE TEST
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

    # Net Profit Margin
    # 200 / 1000 * 100 = 20%
    assert result["net_profit_margin_pct"] == pytest.approx(20.0)

    # Operating Profit Margin
    # 150 / 1000 * 100 = 15%
    assert result["operating_profit_margin_pct"] == pytest.approx(15.0)

    # ROE
    # 200 / (100 + 900) * 100 = 20%
    assert result["return_on_equity_pct"] == pytest.approx(20.0)

    # ROCE
    # EBIT = 150 + 20 = 170
    # Capital employed = 100 + 900 + 500 = 1500
    # ROCE = 170 / 1500 * 100 = 11.3333%
    assert result["return_on_capital_employed_pct"] == pytest.approx(
        11.3333333333
    )

    # ROA
    # 200 / 2000 * 100 = 10%
    assert result["return_on_assets_pct"] == pytest.approx(10.0)

    # OPM source value matches calculated value
    assert result["opm_mismatch_flag"] is False