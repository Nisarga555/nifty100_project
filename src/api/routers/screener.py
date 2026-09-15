from fastapi import APIRouter, HTTPException
from pathlib import Path
import pandas as pd
import math


router = APIRouter(
    prefix="/screener",
    tags=["Screener"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_FILE = PROJECT_ROOT / "output" / "screener_output.xlsx"


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


def load_screener():
    if not OUTPUT_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail="screener_output.xlsx not found",
        )

    try:
        return pd.read_excel(OUTPUT_FILE)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to read screener output: {exc}",
        )


@router.get("")
def screener(
    preset: str | None = None,
    limit: int = 100,
):
    """
    Return screener results.

    Optional:
    - preset: filter by screener preset
    - limit: maximum number of rows
    """

    if limit < 1:
        raise HTTPException(
            status_code=400,
            detail="limit must be greater than 0",
        )

    df = load_screener()

    # Detect likely preset column
    preset_columns = [
        "preset",
        "Preset",
        "screen",
        "Screen",
        "screener",
        "Screener",
    ]

    preset_column = next(
        (column for column in preset_columns if column in df.columns),
        None,
    )

    if preset and preset_column:
        df = df[
            df[preset_column]
            .astype(str)
            .str.strip()
            .str.lower()
            == preset.strip().lower()
        ]

    records = []

    for row in df.head(limit).to_dict(orient="records"):
        records.append(
            {
                str(key): clean_value(value)
                for key, value in row.items()
            }
        )

    return {
        "count": len(records),
        "total_available": len(df),
        "preset": preset,
        "data": records,
    }