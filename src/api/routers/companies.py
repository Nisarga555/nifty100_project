import math
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = PROJECT_ROOT / "reports"


# ============================================================
# HELPERS
# ============================================================


def find_excel_file(filename: str) -> Path:
    """
    Find an Excel source file in data/raw.
    """
    path = RAW_DIR / filename

    if not path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Source file not found: {filename}",
        )

    return path


def load_excel(filename: str, header=1) -> pd.DataFrame:
    """
    Load an Excel source file.
    """
    path = find_excel_file(filename)

    try:
        return pd.read_excel(path, header=header)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read {filename}: {exc}",
        )


def clean_value(value):
    """
    Convert pandas / NumPy values into JSON-safe values.
    """

    if pd.isna(value):
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    return value


def dataframe_to_records(df: pd.DataFrame):
    """
    Convert dataframe rows to JSON-safe dictionaries.
    """

    records = []

    for record in df.to_dict(orient="records"):
        cleaned = {str(key): clean_value(value) for key, value in record.items()}

        records.append(cleaned)

    return records


def normalize_ticker(value) -> str:
    """
    Normalize ticker values for reliable comparison.
    """
    return str(value).strip().upper()


def get_company(ticker: str):
    """
    Find a company in companies.xlsx.
    """

    df = load_excel("companies.xlsx", header=1)

    if "id" not in df.columns:
        raise HTTPException(
            status_code=500,
            detail="companies.xlsx does not contain required 'id' column",
        )

    ticker_normalized = normalize_ticker(ticker)

    matches = df[df["id"].astype(str).str.strip().str.upper() == ticker_normalized]

    if matches.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Company not found: {ticker}",
        )

    return matches.iloc[0]


def get_company_data(
    filename: str,
    ticker: str,
    header=1,
):
    """
    Load a company-level financial source and return
    rows belonging to the requested ticker.
    """

    df = load_excel(filename, header=header)

    if "company_id" not in df.columns:
        raise HTTPException(
            status_code=500,
            detail=(f"{filename} does not contain required " "'company_id' column"),
        )

    ticker_normalized = normalize_ticker(ticker)

    result = df[
        df["company_id"].astype(str).str.strip().str.upper() == ticker_normalized
    ].copy()

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {filename.replace('.xlsx', '')} "
                f"data found for company: {ticker}"
            ),
        )

    return result


# ============================================================
# GET ALL COMPANIES
# ============================================================


@router.get("")
def list_companies():
    """
    Return all NIFTY 100 companies.
    """

    df = load_excel("companies.xlsx", header=1)

    records = dataframe_to_records(df)

    return {
        "count": len(records),
        "data": records,
    }


# ============================================================
# GET ONE COMPANY
# ============================================================


@router.get("/{ticker}")
def company_detail(ticker: str):
    """
    Return company master information.
    """

    company = get_company(ticker)

    return {
        "data": {
            str(key): clean_value(value) for key, value in company.to_dict().items()
        }
    }


# ============================================================
# PROFIT & LOSS
# ============================================================


@router.get("/{ticker}/pl")
def company_profit_and_loss(ticker: str):
    """
    Return Profit & Loss history for a company.
    """

    # Confirm company exists
    get_company(ticker)

    df = get_company_data(
        "profitandloss.xlsx",
        ticker,
        header=1,
    )

    records = dataframe_to_records(df)

    return {
        "ticker": normalize_ticker(ticker),
        "count": len(records),
        "data": records,
    }


# ============================================================
# BALANCE SHEET
# ============================================================


@router.get("/{ticker}/bs")
def company_balance_sheet(ticker: str):
    """
    Return Balance Sheet history for a company.
    """

    # Confirm company exists
    get_company(ticker)

    df = get_company_data(
        "balancesheet.xlsx",
        ticker,
        header=1,
    )

    records = dataframe_to_records(df)

    return {
        "ticker": normalize_ticker(ticker),
        "count": len(records),
        "data": records,
    }


# ============================================================
# CASH FLOW
# ============================================================


@router.get("/{ticker}/cashflow")
def company_cashflow(ticker: str):
    """
    Return Cash Flow history for a company.
    """

    # Confirm company exists
    get_company(ticker)

    df = get_company_data(
        "cashflow.xlsx",
        ticker,
        header=1,
    )

    records = dataframe_to_records(df)

    return {
        "ticker": normalize_ticker(ticker),
        "count": len(records),
        "data": records,
    }


# ============================================================
# FINANCIAL RATIOS
# ============================================================


@router.get("/{ticker}/ratios")
def company_ratios(ticker: str):
    """
    Return calculated financial ratios from SQLite.
    """

    import sqlite3

    db_path = PROJECT_ROOT / "db" / "nifty100.sqlite3"

    if not db_path.exists():
        raise HTTPException(
            status_code=500,
            detail="SQLite database not found",
        )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM financial_ratios
            WHERE UPPER(TRIM(company_id)) = ?
            ORDER BY year
            """,
            (normalize_ticker(ticker),),
        )

        rows = cursor.fetchall()

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )

    finally:
        connection.close()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No ratio data found for company: {ticker}",
        )

    records = []

    for row in rows:
        records.append({key: clean_value(row[key]) for key in row.keys()})

    return {
        "ticker": normalize_ticker(ticker),
        "count": len(records),
        "data": records,
    }


# ============================================================
# TEAR SHEET
# ============================================================


@router.get("/{ticker}/tearsheet")
def company_tearsheet(ticker: str):
    """
    Return the location of the generated company tear sheet.
    """

    # Confirm company exists
    get_company(ticker)

    ticker_normalized = normalize_ticker(ticker)

    candidate_directories = [
        REPORTS_DIR / "tearsheets",
        REPORTS_DIR / "tearsheet",
        REPORTS_DIR,
    ]

    possible_files = []

    for directory in candidate_directories:

        if not directory.exists():
            continue

        possible_files.extend(directory.glob(f"*{ticker_normalized}*.pdf"))

    if not possible_files:

        return {
            "ticker": ticker_normalized,
            "status": "not_found",
            "message": (
                "Company tear sheet was not found " "in the reports directory."
            ),
        }

    pdf_path = possible_files[0]

    return {
        "ticker": ticker_normalized,
        "status": "available",
        "filename": pdf_path.name,
        "path": str(pdf_path),
    }
