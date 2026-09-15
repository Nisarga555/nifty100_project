from fastapi import APIRouter, HTTPException
from pathlib import Path
import pandas as pd
import math


router = APIRouter(
    prefix="/sectors",
    tags=["Sectors"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


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


def load_sectors():
    path = RAW_DIR / "sectors.xlsx"

    if not path.exists():
        raise HTTPException(
            status_code=500,
            detail="sectors.xlsx not found",
        )

    try:
        df = pd.read_excel(path, header=0)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read sectors.xlsx: {exc}",
        )

    required_columns = [
        "company_id",
        "broad_sector",
        "sub_sector",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing sector columns: {missing}",
        )

    return df


def records_from_dataframe(df):
    records = []

    for row in df.to_dict(orient="records"):
        records.append(
            {
                str(key): clean_value(value)
                for key, value in row.items()
            }
        )

    return records


@router.get("")
def list_sectors():
    """
    Return sector summary for NIFTY 100 companies.
    """

    df = load_sectors()

    summary = (
        df.groupby(
            ["broad_sector"],
            dropna=False,
        )
        .agg(
            company_count=("company_id", "nunique"),
            sub_sector_count=("sub_sector", "nunique"),
        )
        .reset_index()
        .sort_values(
            "company_count",
            ascending=False,
        )
    )

    records = records_from_dataframe(summary)

    return {
        "count": len(records),
        "data": records,
    }


@router.get("/{sector}/companies")
def sector_companies(sector: str):
    """
    Return all companies belonging to a broad sector.
    """

    df = load_sectors()

    sector_normalized = sector.strip().lower()

    result = df[
        df["broad_sector"]
        .astype(str)
        .str.strip()
        .str.lower()
        == sector_normalized
    ].copy()

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Sector not found: {sector}",
        )

    result = result.sort_values(
        by=["sub_sector", "company_id"]
    )

    records = records_from_dataframe(result)

    return {
        "sector": result.iloc[0]["broad_sector"],
        "count": len(records),
        "data": records,
    }