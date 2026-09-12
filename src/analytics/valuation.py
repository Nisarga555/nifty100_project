from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "output"


# ============================================================
# EXCEL READER
# ============================================================

def read_clean_excel(path: Path) -> pd.DataFrame:
    """
    Read an Excel file and automatically detect the real
    header row.

    Supports:
        companies.xlsx
        sectors.xlsx
        financial_ratios.xlsx
        market_cap.xlsx

    Some source files contain title rows before the actual
    column headers, so header=None is used first.
    """

    raw = pd.read_excel(
        path,
        header=None,
    )

    header_index = None

    for i in range(min(20, len(raw))):

        values = (
            raw.iloc[i]
            .astype(str)
            .str.strip()
            .str.lower()
            .tolist()
        )

        # ----------------------------------------------------
        # Companies file
        # ----------------------------------------------------

        if (
            "id" in values
            and "company_name" in values
        ):
            header_index = i
            break

        # ----------------------------------------------------
        # Company-year files
        # ----------------------------------------------------

        if (
            "company_id" in values
            and "year" in values
        ):
            header_index = i
            break

        # ----------------------------------------------------
        # Sector file
        # ----------------------------------------------------

        if (
            "company_id" in values
            and (
                "broad_sector" in values
                or "sub_sector" in values
            )
        ):
            header_index = i
            break

    if header_index is None:
        raise ValueError(
            f"Could not detect header row in {path.name}"
        )

    df = pd.read_excel(
        path,
        header=header_index,
    )

    # Remove unnamed columns
    df = df.loc[
        :,
        ~df.columns.astype(str).str.startswith("Unnamed"),
    ]

    # Remove completely empty rows
    df = df.dropna(
        how="all"
    ).copy()

    # Clean column names
    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    return df


# ============================================================
# YEAR PARSER
# ============================================================

def parse_year(value):
    """
    Convert values such as:

        2019
        2020
        Mar 2021
        Dec 2022

    into integer years.
    """

    if pd.isna(value):
        return np.nan

    text = str(value)

    match = pd.Series(
        [text]
    ).str.extract(
        r"(\d{4})"
    ).iloc[0, 0]

    if pd.isna(match):
        return np.nan

    return int(match)


# ============================================================
# NUMERIC HELPER
# ============================================================

def safe_numeric(series):
    """
    Convert a pandas series to numeric values.
    Invalid values become NaN.
    """

    return pd.to_numeric(
        series,
        errors="coerce",
    )


# ============================================================
# FCF YIELD
# ============================================================

def calculate_fcf_yield(
    free_cash_flow,
    market_cap,
):
    """
    FCF Yield = FCF / Market Cap × 100
    """

    fcf = safe_numeric(
        free_cash_flow
    )

    market_cap = safe_numeric(
        market_cap
    )

    return np.where(
        market_cap > 0,
        (
            fcf
            / market_cap
        ) * 100,
        np.nan,
    )


# ============================================================
# VALUATION FLAG
# ============================================================

def valuation_flag(
    pe,
    sector_median_pe,
):
    """
    Valuation rules:

        Caution:
            P/E > 1.5 × sector median

        Discount:
            P/E < 0.7 × sector median

        Fair:
            otherwise

        Unavailable:
            insufficient valuation data
    """

    if pd.isna(pe):
        return "Unavailable"

    if pd.isna(sector_median_pe):
        return "Unavailable"

    if sector_median_pe <= 0:
        return "Unavailable"

    if pe > (
        sector_median_pe * 1.5
    ):
        return "Caution"

    if pe < (
        sector_median_pe * 0.7
    ):
        return "Discount"

    return "Fair"


# ============================================================
# BUILD VALUATION SUMMARY
# ============================================================

def build_valuation_summary():

    # ========================================================
    # LOAD SOURCE FILES
    # ========================================================

    companies = read_clean_excel(
        RAW_DIR / "companies.xlsx"
    )

    sectors = read_clean_excel(
        RAW_DIR / "sectors.xlsx"
    )

    ratios = read_clean_excel(
        RAW_DIR / "financial_ratios.xlsx"
    )

    market_cap = read_clean_excel(
        RAW_DIR / "market_cap.xlsx"
    )

    # ========================================================
    # CLEAN COMPANY IDS
    # ========================================================

    companies["id"] = (
        companies["id"]
        .astype(str)
        .str.strip()
    )

    sectors["company_id"] = (
        sectors["company_id"]
        .astype(str)
        .str.strip()
    )

    ratios["company_id"] = (
        ratios["company_id"]
        .astype(str)
        .str.strip()
    )

    market_cap["company_id"] = (
        market_cap["company_id"]
        .astype(str)
        .str.strip()
    )

    # ========================================================
    # PARSE YEARS
    # ========================================================

    ratios["year_num"] = (
        ratios["year"]
        .apply(parse_year)
    )

    market_cap["year_num"] = (
        market_cap["year"]
        .apply(parse_year)
    )

    # ========================================================
    # NUMERIC CONVERSION
    # ========================================================

    if "free_cash_flow_cr" in ratios.columns:

        ratios["free_cash_flow_cr"] = safe_numeric(
            ratios["free_cash_flow_cr"]
        )

    for column in [
        "market_cap_crore",
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
    ]:

        if column in market_cap.columns:

            market_cap[column] = safe_numeric(
                market_cap[column]
            )

    # ========================================================
    # LATEST MARKET CAP / VALUATION DATA
    # ========================================================

    market_cap = market_cap.sort_values(
        [
            "company_id",
            "year_num",
        ],
        ascending=[
            True,
            False,
        ],
        na_position="last",
    )

    latest_market_cap = (
        market_cap
        .drop_duplicates(
            "company_id",
            keep="first",
        )
        .copy()
    )

    # ========================================================
    # LATEST FCF
    # ========================================================

    ratios = ratios.sort_values(
        [
            "company_id",
            "year_num",
        ],
        ascending=[
            True,
            False,
        ],
        na_position="last",
    )

    latest_fcf = (
        ratios[
            [
                "company_id",
                "year_num",
                "free_cash_flow_cr",
            ]
        ]
        .drop_duplicates(
            "company_id",
            keep="first",
        )
        .copy()
    )

    # ========================================================
    # BASE COMPANY DATA
    # ========================================================

    result = companies[
        [
            "id",
            "company_name",
        ]
    ].rename(
        columns={
            "id": "company_id",
        }
    )

    # ========================================================
    # SECTOR DATA
    # ========================================================

    sector_data = sectors[
        [
            "company_id",
            "broad_sector",
        ]
    ].copy()

    sector_data = sector_data.drop_duplicates(
        "company_id"
    )

    sector_data = sector_data.rename(
        columns={
            "broad_sector": "sector",
        }
    )

    result = result.merge(
        sector_data[
            [
                "company_id",
                "sector",
            ]
        ],
        on="company_id",
        how="left",
    )

    # ========================================================
    # MERGE MARKET CAP DATA
    # ========================================================

    result = result.merge(
        latest_market_cap[
            [
                "company_id",
                "market_cap_crore",
                "pe_ratio",
                "pb_ratio",
                "ev_ebitda",
            ]
        ],
        on="company_id",
        how="left",
    )

    # ========================================================
    # MERGE FCF DATA
    # ========================================================

    result = result.merge(
        latest_fcf[
            [
                "company_id",
                "free_cash_flow_cr",
            ]
        ],
        on="company_id",
        how="left",
    )

    # ========================================================
    # FCF YIELD
    # ========================================================

    result["fcf_yield_pct"] = calculate_fcf_yield(
        result["free_cash_flow_cr"],
        result["market_cap_crore"],
    )

    # ========================================================
    # 5-YEAR MEDIAN P/E
    # ========================================================

    pe_history = market_cap[
        [
            "company_id",
            "year_num",
            "pe_ratio",
        ]
    ].copy()

    # Only positive P/E values are meaningful
    pe_history = pe_history[
        pe_history["pe_ratio"].notna()
        & (
            pe_history["pe_ratio"] > 0
        )
    ].copy()

    pe_history = pe_history.sort_values(
        [
            "company_id",
            "year_num",
        ]
    )

    five_year_pe = (
        pe_history
        .groupby("company_id")
        .tail(5)
        .groupby("company_id")["pe_ratio"]
        .median()
        .reset_index()
        .rename(
            columns={
                "pe_ratio": "5yr_median_PE",
            }
        )
    )

    result = result.merge(
        five_year_pe,
        on="company_id",
        how="left",
    )

    # ========================================================
    # SECTOR MEDIAN P/E
    # ========================================================

    sector_pe = result[
        [
            "company_id",
            "sector",
            "pe_ratio",
        ]
    ].copy()

    sector_pe = sector_pe[
        sector_pe["pe_ratio"].notna()
        & (
            sector_pe["pe_ratio"] > 0
        )
    ].copy()

    sector_medians = (
        sector_pe
        .groupby("sector")["pe_ratio"]
        .median()
        .rename(
            "sector_median_pe"
        )
        .reset_index()
    )

    result = result.merge(
        sector_medians,
        on="sector",
        how="left",
    )

    # ========================================================
    # P/E VS SECTOR MEDIAN
    # ========================================================

    result[
        "PE_vs_sector_median_pct"
    ] = np.where(
        result["pe_ratio"].notna()
        & result[
            "sector_median_pe"
        ].notna()
        & (
            result[
                "sector_median_pe"
            ] > 0
        ),
        (
            (
                result["pe_ratio"]
                /
                result[
                    "sector_median_pe"
                ]
            )
            - 1
        ) * 100,
        np.nan,
    )

    # ========================================================
    # VALUATION FLAGS
    # ========================================================

    result["flag"] = result.apply(
        lambda row: valuation_flag(
            row["pe_ratio"],
            row[
                "sector_median_pe"
            ],
        ),
        axis=1,
    )

    # ========================================================
    # FINAL OUTPUT COLUMNS
    # ========================================================

    final = result[
        [
            "company_id",
            "company_name",
            "sector",
            "pe_ratio",
            "pb_ratio",
            "ev_ebitda",
            "fcf_yield_pct",
            "5yr_median_PE",
            "PE_vs_sector_median_pct",
            "flag",
        ]
    ].copy()

    # Rename valuation columns
    final = final.rename(
        columns={
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "ev_ebitda": "EV/EBITDA",
        }
    )

    # Sort alphabetically
    final = final.sort_values(
        "company_name",
        na_position="last",
    ).reset_index(
        drop=True
    )

    return final


# ============================================================
# GENERATE OUTPUT FILES
# ============================================================

def generate_valuation_files():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Build complete summary
    summary = build_valuation_summary()

    # ========================================================
    # VALIDATION
    # ========================================================

    if len(summary) != 92:
        print(
            "WARNING:"
            f" Expected 92 companies but found "
            f"{len(summary)}."
        )

    duplicate_count = (
        summary["company_id"]
        .duplicated()
        .sum()
    )

    if duplicate_count > 0:
        print(
            "WARNING:"
            f" Found {duplicate_count} duplicate company IDs."
        )

    # ========================================================
    # EXCEL OUTPUT
    # ========================================================

    summary_path = (
        OUTPUT_DIR
        / "valuation_summary.xlsx"
    )

    summary.to_excel(
        summary_path,
        index=False,
    )

    # ========================================================
    # FLAG CSV
    # ========================================================

    flags = summary[
        summary["flag"].isin(
            [
                "Caution",
                "Discount",
            ]
        )
    ].copy()

    flags_path = (
        OUTPUT_DIR
        / "valuation_flags.csv"
    )

    flags.to_csv(
        flags_path,
        index=False,
    )

    return (
        summary,
        flags,
        summary_path,
        flags_path,
    )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    (
        summary,
        flags,
        summary_path,
        flags_path,
    ) = generate_valuation_files()

    print()
    print("=" * 70)
    print("DAY 26 — VALUATION OUTPUT")
    print("=" * 70)

    print(
        f"Companies       : {len(summary)}"
    )

    print(
        f"Duplicate IDs   : "
        f"{summary['company_id'].duplicated().sum()}"
    )

    print(
        f"Caution         : "
        f"{(
            summary['flag'] == 'Caution'
        ).sum()}"
    )

    print(
        f"Discount        : "
        f"{(
            summary['flag'] == 'Discount'
        ).sum()}"
    )

    print(
        f"Fair            : "
        f"{(
            summary['flag'] == 'Fair'
        ).sum()}"
    )

    print(
        f"Unavailable     : "
        f"{(
            summary['flag'] == 'Unavailable'
        ).sum()}"
    )

    print()

    print(
        f"Excel created   : {summary_path}"
    )

    print(
        f"CSV created     : {flags_path}"
    )

    print("=" * 70)