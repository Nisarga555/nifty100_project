from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Documents"])

BASE_DIR = Path.cwd()
DOCUMENTS_FILE = BASE_DIR / "data" / "raw" / "documents.xlsx"


@router.get("/companies/{ticker}/documents")
def get_company_documents(ticker: str):
    ticker = ticker.upper().strip()

    if not DOCUMENTS_FILE.exists():
        raise HTTPException(
            status_code=404, detail=f"documents.xlsx not found at {DOCUMENTS_FILE}"
        )

    try:
        df = pd.read_excel(DOCUMENTS_FILE, header=1)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read documents.xlsx: {exc}"
        )

    if "company_id" not in df.columns:
        raise HTTPException(
            status_code=500, detail="documents.xlsx missing company_id column"
        )

    company_df = df[
        df["company_id"].astype(str).str.upper().str.strip() == ticker
    ].copy()

    if company_df.empty:
        raise HTTPException(
            status_code=404, detail=f"No documents found for company '{ticker}'"
        )

    company_df = company_df.where(pd.notna(company_df), None)

    return {
        "ticker": ticker,
        "count": len(company_df),
        "data": company_df.to_dict(orient="records"),
    }
