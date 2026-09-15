from fastapi import APIRouter, HTTPException
from pathlib import Path
import sqlite3
import pandas as pd
import math


router = APIRouter(
    tags=["Peers"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROJECT_ROOT / "db" / "nifty100.sqlite3"


def clean_value(value):
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

    return value


def normalize(value):
    return str(value).strip().lower()


def load_peer_groups():
    path = RAW_DIR / "peer_groups.xlsx"

    if not path.exists():
        raise HTTPException(
            status_code=500,
            detail="peer_groups.xlsx not found",
        )

    try:
        return pd.read_excel(path, header=0)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read peer_groups.xlsx: {exc}",
        )


def dataframe_to_records(df):
    records = []

    for row in df.to_dict(orient="records"):
        records.append(
            {
                str(key): clean_value(value)
                for key, value in row.items()
            }
        )

    return records


def load_percentiles(company_ids):
    """
    Load peer percentile data from SQLite.

    Actual peer_percentiles schema:
    company_id
    peer_group_name
    metric
    value
    percentile_rank
    year
    """

    if not company_ids:
        return []

    if not DB_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="SQLite database not found",
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:

        placeholders = ",".join(
            ["?"] * len(company_ids)
        )

        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT
                company_id,
                peer_group_name,
                metric,
                value,
                percentile_rank,
                year
            FROM peer_percentiles
            WHERE UPPER(TRIM(company_id))
            IN ({placeholders})
            ORDER BY
                peer_group_name,
                company_id,
                metric,
                year
            """,
            company_ids,
        )

        rows = cursor.fetchall()

        return [
            {
                key: clean_value(row[key])
                for key in row.keys()
            }
            for row in rows
        ]

    except sqlite3.Error as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Database error: {exc}",
        )

    finally:

        connection.close()


# ============================================================
# PEER GROUP
# ============================================================

@router.get("/peers/{group_name}")
def peer_group(group_name: str):
    """
    Return companies belonging to a peer group,
    together with percentile metrics.
    """

    df = load_peer_groups()

    required_columns = [
        "id",
        "peer_group_name",
        "company_id",
        "is_benchmark",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise HTTPException(
            status_code=500,
            detail=f"Missing peer group columns: {missing}",
        )

    result = df[
        df["peer_group_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        == normalize(group_name)
    ].copy()

    if result.empty:

        raise HTTPException(
            status_code=404,
            detail=f"Peer group not found: {group_name}",
        )

    result["company_id"] = (
        result["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    company_ids = result["company_id"].tolist()

    percentiles = load_percentiles(
        company_ids
    )

    return {
        "peer_group": str(
            result.iloc[0]["peer_group_name"]
        ),
        "company_count": len(result),
        "companies": dataframe_to_records(result),
        "percentiles": percentiles,
    }


# ============================================================
# COMPANY PEER COMPARISON
# ============================================================

@router.get("/companies/{ticker}/peers/compare")
def peer_comparison(ticker: str):
    """
    Compare a company against its assigned peer group.
    """

    ticker = ticker.strip().upper()

    df = load_peer_groups()

    required_columns = [
        "id",
        "peer_group_name",
        "company_id",
        "is_benchmark",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise HTTPException(
            status_code=500,
            detail=f"Missing peer group columns: {missing}",
        )

    company_match = df[
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        == ticker
    ]

    if company_match.empty:

        raise HTTPException(
            status_code=404,
            detail=f"No peer group found for company: {ticker}",
        )

    group_name = str(
        company_match.iloc[0]["peer_group_name"]
    )

    peer_df = df[
        df["peer_group_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        == normalize(group_name)
    ].copy()

    peer_df["company_id"] = (
        peer_df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    company_ids = peer_df["company_id"].tolist()

    percentiles = load_percentiles(
        company_ids
    )

    return {
        "ticker": ticker,
        "peer_group": group_name,
        "peer_count": len(peer_df),
        "peers": dataframe_to_records(peer_df),
        "percentiles": percentiles,
    }