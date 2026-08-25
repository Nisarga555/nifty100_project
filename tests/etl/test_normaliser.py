import pandas as pd

from src.etl.normaliser import (
    normalize_year,
    normalize_ticker,
    normalize_numeric,
    normalize_date,
    normalize_boolean,
    clean_column_name,
)


# ============================================================
# YEAR / REPORTING PERIOD TESTS
# ============================================================

def test_normalize_year_integer():
    assert normalize_year(2024) == 2024


def test_normalize_year_string():
    assert normalize_year("2024") == 2024


def test_normalize_year_december():
    assert normalize_year("Dec 2012") == "2012-12"


def test_normalize_year_mar_short():
    assert normalize_year("Mar-13") == "2013-03"


def test_normalize_year_mar_full():
    assert normalize_year("Mar 2014") == "2014-03"


def test_normalize_year_september():
    assert normalize_year("Sep 2024") == "2024-09"


def test_normalize_year_june():
    assert normalize_year("Jun 2024") == "2024-06"


def test_normalize_year_none():
    assert normalize_year(None) is None


# ============================================================
# TICKER TESTS
# ============================================================

def test_normalize_ticker_lowercase():
    assert normalize_ticker("tcs") == "TCS"


def test_normalize_ticker_spaces():
    assert normalize_ticker("  TCS  ") == "TCS"


def test_normalize_ticker_mixed_case():
    assert normalize_ticker("hDfCbAnK") == "HDFCBANK"


def test_normalize_ticker_none():
    assert normalize_ticker(None) is None


# ============================================================
# NUMERIC TESTS
# ============================================================

def test_normalize_numeric_integer():
    assert normalize_numeric(100) == 100.0


def test_normalize_numeric_string():
    assert normalize_numeric("100.5") == 100.5


def test_normalize_numeric_comma():
    assert normalize_numeric("1,234") == 1234.0


def test_normalize_numeric_percentage():
    assert normalize_numeric("25%") == 25.0


def test_normalize_numeric_negative():
    assert normalize_numeric("(500)") == -500.0


def test_normalize_numeric_dash():
    assert normalize_numeric("-") is None


def test_normalize_numeric_none():
    assert normalize_numeric(None) is None


# ============================================================
# BOOLEAN TESTS
# ============================================================

def test_normalize_boolean_true():
    assert normalize_boolean("True") is True


def test_normalize_boolean_yes():
    assert normalize_boolean("yes") is True


def test_normalize_boolean_false():
    assert normalize_boolean("False") is False


def test_normalize_boolean_no():
    assert normalize_boolean("no") is False


# ============================================================
# COLUMN NAME TESTS
# ============================================================

def test_clean_column_name():
    assert clean_column_name(
        "Operating Profit Margin %"
    ) == "operating_profit_margin"


def test_clean_column_name_spaces():
    assert clean_column_name(
        "Company Name"
    ) == "company_name"


def test_clean_column_name_special_chars():
    assert clean_column_name(
        "EPS (%)"
    ) == "eps"