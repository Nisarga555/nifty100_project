from fastapi import APIRouter, HTTPException
import pandas as pd
from pathlib import Path

router = APIRouter(tags=["Valuation"])

# Project root:
# nifty100_project/
BASE_DIR = Path.cwd()

MARKET_CAP_FILE = BASE_DIR / "data" / "raw" / "market_cap.xlsx"


@router.get("/market-cap/{ticker}")
def get_market_cap(ticker: str):
    ticker = ticker.upper().strip()

    if not MARKET_CAP_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=f"market_cap.xlsx not found at {MARKET_CAP_FILE}"
        )

    try:
        df = pd.read_excel(
            MARKET_CAP_FILE,
            header=0
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read market_cap.xlsx: {exc}"
        )

    required_columns = {
        "id",
        "company_id",
        "year",
        "market_cap_crore",
        "enterprise_value_crore",
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "dividend_yield_pct",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"market_cap.xlsx missing columns: {sorted(missing)}"
        )

    company_df = df[
        df["company_id"]
        .astype(str)
        .str.upper()
        .str.strip()
        == ticker
    ].copy()

    if company_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Company '{ticker}' not found in market cap data"
        )

    company_df = company_df.sort_values("year")

    company_df = company_df.where(
        pd.notna(company_df),
        None
    )

    return {
        "ticker": ticker,
        "count": len(company_df),
        "data": company_df.to_dict(orient="records"),
    }