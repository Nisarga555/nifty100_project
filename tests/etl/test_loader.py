import pytest
import pandas as pd

from src.etl.loader import (
    SOURCE_FILES,
    load_source,
    load_all_sources,
    read_excel_file,
)
from src.etl.normaliser import normalize_dataframe


def test_source_file_count():
    assert len(SOURCE_FILES) == 12


def test_companies_file_exists():
    assert SOURCE_FILES["companies"] == "companies.xlsx"


def test_profitandloss_file_exists():
    assert SOURCE_FILES["profitandloss"] == "profitandloss.xlsx"


def test_balancesheet_file_exists():
    assert SOURCE_FILES["balancesheet"] == "balancesheet.xlsx"


def test_cashflow_file_exists():
    assert SOURCE_FILES["cashflow"] == "cashflow.xlsx"


def test_stock_prices_file_exists():
    assert SOURCE_FILES["stock_prices"] == "stock_prices.xlsx"


def test_financial_ratios_file_exists():
    assert SOURCE_FILES["financial_ratios"] == "financial_ratios.xlsx"


def test_market_cap_file_exists():
    assert SOURCE_FILES["market_cap"] == "market_cap.xlsx"


def test_companies_row_count():
    df = load_source("companies")
    assert len(df) == 92


def test_profitandloss_row_count():
    df = load_source("profitandloss")
    assert len(df) == 1276


def test_balancesheet_row_count():
    df = load_source("balancesheet")
    assert len(df) == 1312


def test_cashflow_row_count():
    df = load_source("cashflow")
    assert len(df) == 1187


def test_stock_prices_row_count():
    df = load_source("stock_prices")
    assert len(df) == 5520


def test_invalid_source_raises_error():
    with pytest.raises(ValueError):
        load_source("invalid_dataset")


def test_normalized_columns_are_lowercase():
    df = load_source("profitandloss")

    for column in df.columns:
        assert column == column.lower()


def test_profitandloss_required_columns():
    df = load_source("profitandloss")

    required = {
        "id",
        "company_id",
        "year",
        "sales",
        "operating_profit",
        "net_profit",
    }

    assert required.issubset(set(df.columns))