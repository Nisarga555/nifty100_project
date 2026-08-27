
"""
SQLite database utilities for the NIFTY 100 project.

Sprint 2 - Day 12
"""

from pathlib import Path
import sqlite3


DB_DIR = Path("db")
DB_PATH = DB_DIR / "nifty100.sqlite3"


def get_connection(db_path=DB_PATH):
    """
    Create and return a SQLite connection.
    """

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)

    return connection


def create_financial_ratios_table(connection):
    """
    Create the financial_ratios table used by the analytics layer.

    The table contains:
        - source/company identifiers
        - profitability KPIs
        - leverage KPIs
        - efficiency KPIs
        - cash-flow KPIs
        - growth KPIs
        - composite quality score
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_ratios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            company_id TEXT NOT NULL,
            year TEXT NOT NULL,

            net_profit_margin_pct REAL,
            operating_profit_margin_pct REAL,
            return_on_equity_pct REAL,
            return_on_capital_employed_pct REAL,
            return_on_assets_pct REAL,

            debt_to_equity REAL,
            high_leverage_flag INTEGER,

            interest_coverage REAL,
            icr_label TEXT,
            icr_warning_flag INTEGER,

            net_debt_cr REAL,
            asset_turnover REAL,

            free_cash_flow_cr REAL,
            capex_cr REAL,
            capex_intensity_pct REAL,
            capex_intensity_label TEXT,

            fcf_conversion_rate_pct REAL,

            cfo_quality_score REAL,
            cfo_quality_label TEXT,

            earnings_per_share REAL,
            book_value_per_share REAL,
            dividend_payout_ratio_pct REAL,
            total_debt_cr REAL,
            cash_from_operations_cr REAL,

            revenue_cagr_3yr REAL,
            revenue_cagr_3yr_flag TEXT,
            revenue_cagr_5yr REAL,
            revenue_cagr_5yr_flag TEXT,
            revenue_cagr_10yr REAL,
            revenue_cagr_10yr_flag TEXT,

            pat_cagr_3yr REAL,
            pat_cagr_3yr_flag TEXT,
            pat_cagr_5yr REAL,
            pat_cagr_5yr_flag TEXT,
            pat_cagr_10yr REAL,
            pat_cagr_10yr_flag TEXT,

            eps_cagr_3yr REAL,
            eps_cagr_3yr_flag TEXT,
            eps_cagr_5yr REAL,
            eps_cagr_5yr_flag TEXT,
            eps_cagr_10yr REAL,
            eps_cagr_10yr_flag TEXT,

            composite_quality_score REAL,

            UNIQUE(company_id, year)
        )
        """
    )

    connection.commit()


def clear_financial_ratios(connection):
    """
    Remove previously generated ratio rows.

    This makes the Day 12 population script repeatable.
    """

    connection.execute(
        "DELETE FROM financial_ratios"
    )

    connection.commit()


def get_financial_ratio_count(connection):
    """
    Return number of rows in financial_ratios.
    """

    cursor = connection.execute(
        "SELECT COUNT(*) FROM financial_ratios"
    )

    return cursor.fetchone()[0]


def get_financial_ratio_columns(connection):
    """
    Return financial_ratios column names.
    """

    cursor = connection.execute(
        "PRAGMA table_info(financial_ratios)"
    )

    return [
        row[1]
        for row in cursor.fetchall()
    ]