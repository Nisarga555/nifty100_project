from pathlib import Path
import re
import sqlite3

import pandas as pd
import streamlit as st


# =============================================================================
# PROJECT PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DB_PATH = PROJECT_ROOT / "db" / "nifty100.sqlite3"
RAW_PATH = PROJECT_ROOT / "data" / "raw"


# =============================================================================
# EXCEL LOADER
# =============================================================================

def _read_clean_excel(filename: str) -> pd.DataFrame:
    """
    Read one of the project's Excel source files.

    Several source workbooks contain a title row before the actual
    column-header row. This function automatically detects the real
    header row instead of assuming row 1 is the header.
    """

    path = RAW_PATH / filename

    if not path.exists():
        return pd.DataFrame()

    try:
        raw = pd.read_excel(
            path,
            header=None,
        )

        if raw.empty:
            return pd.DataFrame()

        header_row = None

        # ---------------------------------------------------------------------
        # Detect the real header row.
        # ---------------------------------------------------------------------

        for i in range(min(len(raw), 20)):

            values = (
                raw.iloc[i]
                .astype(str)
                .str.strip()
                .str.lower()
                .tolist()
            )

            # Company master
            if (
                "id" in values
                and "company_name" in values
            ):
                header_row = i
                break

            # Most financial/source files
            if "company_id" in values:
                header_row = i
                break

            # Peer groups
            if "peer_group_name" in values:
                header_row = i
                break

        # ---------------------------------------------------------------------
        # Build dataframe using detected header.
        # ---------------------------------------------------------------------

        if header_row is None:

            data = pd.read_excel(
                path
            )

        else:

            headers = raw.iloc[
                header_row
            ].tolist()

            data = raw.iloc[
                header_row + 1:
            ].copy()

            data.columns = headers

            data = data.reset_index(
                drop=True
            )

        # ---------------------------------------------------------------------
        # Remove unnamed columns.
        # ---------------------------------------------------------------------

        data = data.loc[
            :,
            ~data.columns
            .astype(str)
            .str.strip()
            .str.lower()
            .str.startswith("unnamed"),
        ]

        # ---------------------------------------------------------------------
        # Remove completely empty rows.
        # ---------------------------------------------------------------------

        data = data.dropna(
            how="all"
        ).reset_index(
            drop=True
        )

        return data

    except Exception:
        return pd.DataFrame()


# =============================================================================
# GENERIC HELPERS
# =============================================================================

def _filter_company(
    data: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """
    Filter a dataframe using company_id.
    """

    if (
        data.empty
        or "company_id" not in data.columns
    ):
        return pd.DataFrame()

    return data.loc[
        data["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        ==
        str(ticker)
        .strip()
        .upper()
    ].copy()


def _parse_year(value):
    """
    Extract a four-digit year from values such as:

        Mar 2024
        2023-03
        Sep 2022
        Dec 2021
    """

    if pd.isna(value):
        return None

    match = re.search(
        r"(19|20)\d{2}",
        str(value),
    )

    if match:
        return int(
            match.group(0)
        )

    return None


# =============================================================================
# COMPANY MASTER
# =============================================================================

@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """
    Load the 92-company master dataset.
    """

    return _read_clean_excel(
        "companies.xlsx"
    )


# =============================================================================
# FINANCIAL RATIOS
# =============================================================================

@st.cache_data(ttl=600)
def get_ratios(
    ticker: str,
    year=None,
) -> pd.DataFrame:
    """
    Load financial ratio history for a company.

    If year is supplied, only that year is returned.
    """

    if not DB_PATH.exists():
        return pd.DataFrame()

    query = """
        SELECT *
        FROM financial_ratios
        WHERE UPPER(TRIM(company_id))
              = UPPER(TRIM(?))
    """

    params = [ticker]

    if year is not None:

        query += """
            AND year = ?
        """

        params.append(
            str(year)
        )

    query += """
        ORDER BY year
    """

    try:

        with sqlite3.connect(
            DB_PATH
        ) as conn:

            return pd.read_sql_query(
                query,
                conn,
                params=params,
            )

    except Exception:

        return pd.DataFrame()


# =============================================================================
# PROFIT & LOSS
# =============================================================================

@st.cache_data(ttl=600)
def get_pl(
    ticker: str,
) -> pd.DataFrame:
    """
    Load Profit & Loss history for a company.
    """

    return _filter_company(
        _read_clean_excel(
            "profitandloss.xlsx"
        ),
        ticker,
    )


# =============================================================================
# BALANCE SHEET
# =============================================================================

@st.cache_data(ttl=600)
def get_bs(
    ticker: str,
) -> pd.DataFrame:
    """
    Load Balance Sheet history for a company.
    """

    return _filter_company(
        _read_clean_excel(
            "balancesheet.xlsx"
        ),
        ticker,
    )


# =============================================================================
# CASH FLOW
# =============================================================================

@st.cache_data(ttl=600)
def get_cf(
    ticker: str,
) -> pd.DataFrame:
    """
    Load Cash Flow history for a company.
    """

    return _filter_company(
        _read_clean_excel(
            "cashflow.xlsx"
        ),
        ticker,
    )


# =============================================================================
# SECTORS
# =============================================================================

@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """
    Load sector and sub-sector assignments.
    """

    return _read_clean_excel(
        "sectors.xlsx"
    )


# =============================================================================
# PEER GROUPS
# =============================================================================

@st.cache_data(ttl=600)
def get_peers(
    group_name: str,
) -> pd.DataFrame:
    """
    Load companies belonging to a peer group.
    """

    data = _read_clean_excel(
        "peer_groups.xlsx"
    )

    if (
        data.empty
        or "peer_group_name"
        not in data.columns
    ):
        return pd.DataFrame()

    return data.loc[
        data["peer_group_name"]
        .astype(str)
        .str.strip()
        ==
        str(group_name)
        .strip()
    ].copy()


# =============================================================================
# VALUATION
# =============================================================================

@st.cache_data(ttl=600)
def get_valuation(
    ticker: str,
) -> pd.DataFrame:
    """
    Load valuation information from valuation_summary.xlsx.

    Returns an empty dataframe if the valuation workbook has not
    been generated yet.
    """

    path = (
        PROJECT_ROOT
        / "output"
        / "valuation_summary.xlsx"
    )

    if not path.exists():
        return pd.DataFrame()

    try:

        data = pd.read_excel(
            path
        )

        # Valuation workbook uses company_id.
        return _filter_company(
            data,
            ticker,
        )

    except Exception:

        return pd.DataFrame()


# =============================================================================
# PROS & CONS
# =============================================================================

@st.cache_data(ttl=600)
def get_pros_cons(
    ticker: str,
) -> pd.DataFrame:
    """
    Load company pros and cons.
    """

    return _filter_company(
        _read_clean_excel(
            "prosandcons.xlsx"
        ),
        ticker,
    )


# =============================================================================
# MARKET CAP
# =============================================================================

@st.cache_data(ttl=600)
def get_market_cap() -> pd.DataFrame:
    """
    Load market-cap source data.
    """

    return _read_clean_excel(
        "market_cap.xlsx"
    )


# =============================================================================
# ANNUAL REPORTS / DOCUMENTS
# =============================================================================

@st.cache_data(ttl=600)
def get_documents(
    ticker: str,
) -> pd.DataFrame:
    """
    Load annual-report/document records for a company.
    """

    return _filter_company(
        _read_clean_excel(
            "documents.xlsx"
        ),
        ticker,
    )


# =============================================================================
# PEER PERCENTILES
# =============================================================================

@st.cache_data(ttl=600)
def get_peer_percentiles(
    peer_group_name: str | None = None,
    ticker: str | None = None,
) -> pd.DataFrame:
    """
    Load peer percentile rankings from SQLite.

    Optional filters:

        peer_group_name
        ticker / company_id
    """

    if not DB_PATH.exists():
        return pd.DataFrame()

    query = """
        SELECT
            company_id,
            peer_group_name,
            metric,
            value,
            percentile_rank,
            year
        FROM peer_percentiles
        WHERE 1 = 1
    """

    params = []

    if peer_group_name is not None:

        query += """
            AND peer_group_name = ?
        """

        params.append(
            peer_group_name
        )

    if ticker is not None:

        query += """
            AND company_id = ?
        """

        params.append(
            ticker
        )

    query += """
        ORDER BY
            peer_group_name,
            company_id,
            metric
    """

    try:

        with sqlite3.connect(
            DB_PATH
        ) as conn:

            return pd.read_sql_query(
                query,
                conn,
                params=params,
            )

    except Exception:

        return pd.DataFrame()


# =============================================================================
# ALL PEER GROUP NAMES
# =============================================================================

@st.cache_data(ttl=600)
def get_all_peer_groups() -> list[str]:
    """
    Return all unique peer-group names.
    """

    data = _read_clean_excel(
        "peer_groups.xlsx"
    )

    if (
        data.empty
        or "peer_group_name"
        not in data.columns
    ):
        return []

    return sorted(
        data["peer_group_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_database_path() -> Path:
    """
    Return SQLite database path.
    """

    return DB_PATH


def get_project_root() -> Path:
    """
    Return project root directory.
    """

    return PROJECT_ROOT


def extract_year(value):
    """
    Public helper used by dashboard pages to extract
    a four-digit year from financial-period values.
    """

    return _parse_year(value)