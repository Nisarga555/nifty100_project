from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Portfolio"])

BASE_DIR = Path.cwd()
PORTFOLIO_FILE = BASE_DIR / "output" / "portfolio_stats.csv"


@router.get("/portfolio/stats")
def get_portfolio_stats():
    if not PORTFOLIO_FILE.exists():
        raise HTTPException(
            status_code=404, detail=f"portfolio_stats.csv not found at {PORTFOLIO_FILE}"
        )

    try:
        df = pd.read_csv(PORTFOLIO_FILE)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read portfolio_stats.csv: {exc}"
        )

    df = df.where(pd.notna(df), None)

    return {
        "count": len(df),
        "data": df.to_dict(orient="records"),
    }
