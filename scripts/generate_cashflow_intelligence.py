"""
Sprint 5 - Day 31
Cash Flow Intelligence Generator

Outputs:
    output/cashflow_intelligence.xlsx
    output/distress_alerts.csv

Rules:
    - Master universe comes from sectors.xlsx (92 companies).
    - Annual March records only.
    - September and TTM records are excluded.
    - Missing source data is represented as unavailable/blank.
    - No financial values are fabricated.
"""

from pathlib import Path
import math
import re

import pandas as pd

from src.analytics.cashflow_kpis import (
    free_cash_flow,
    cfo_pat_ratio,
    calculate_cfo_quality_score,
    classify_cfo_quality,
    capex_intensity,
    classify_capex_intensity,
    fcf_conversion_rate,
    capital_allocation_pattern,
)


# =====================================================================
# PATHS
# =====================================================================

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "output"

OUTPUT.mkdir(parents=True, exist_ok=True)

PL_FILE = RAW / "profitandloss.xlsx"
BS_FILE = RAW / "balancesheet.xlsx"
CF_FILE = RAW / "cashflow.xlsx"
SECTOR_FILE = RAW / "sectors.xlsx"


# =====================================================================
# HELPERS
# =====================================================================

def to_float(value):
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        value = float(value)

        if math.isnan(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def normalize_company_id(value):
    """Normalize company IDs."""

    if value is None:
        return None

    text = str(value).strip().upper()

    if not text or text == "NAN":
        return None

    return text


def normalize_year(value):
    """
    Convert annual March source labels to integer years.

    Accepted:
        Mar 2024
        Mar-24
        Mar-2024

    Rejected:
        Sep 2024
        TTM
        1 Year
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if not text.lower().startswith("mar"):
        return None

    # Four-digit year.
    match = re.search(r"(20\d{2})", text)

    if match:
        return int(match.group(1))

    # Two-digit year.
    match = re.search(r"(?:-| )(\d{2})$", text)

    if match:
        year = int(match.group(1))

        if year >= 50:
            return 1900 + year

        return 2000 + year

    return None


def clean_numeric_columns(df, columns):
    """Convert selected columns to numeric."""

    for column in columns:

        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


# =====================================================================
# LOAD SOURCES
# =====================================================================

def load_sources():

    print("Loading source data...")

    # ---------------------------------------------------------------
    # Source headers
    # ---------------------------------------------------------------

    pl = pd.read_excel(
        PL_FILE,
        header=1,
    )

    bs = pd.read_excel(
        BS_FILE,
        header=1,
    )

    cf = pd.read_excel(
        CF_FILE,
        header=1,
    )

    sectors = pd.read_excel(
        SECTOR_FILE,
        header=0,
    )

    # ---------------------------------------------------------------
    # Normalize IDs
    # ---------------------------------------------------------------

    for df in (pl, bs, cf, sectors):

        df["company_id"] = df[
            "company_id"
        ].apply(normalize_company_id)

    # ---------------------------------------------------------------
    # Normalize years
    # ---------------------------------------------------------------

    pl["year_num"] = pl["year"].apply(
        normalize_year
    )

    bs["year_num"] = bs["year"].apply(
        normalize_year
    )

    cf["year_num"] = cf["year"].apply(
        normalize_year
    )

    # ---------------------------------------------------------------
    # Keep annual March records only
    # ---------------------------------------------------------------

    pl = pl[
        pl["year_num"].notna()
    ].copy()

    bs = bs[
        bs["year_num"].notna()
    ].copy()

    cf = cf[
        cf["year_num"].notna()
    ].copy()

    pl["year_num"] = pl[
        "year_num"
    ].astype(int)

    bs["year_num"] = bs[
        "year_num"
    ].astype(int)

    cf["year_num"] = cf[
        "year_num"
    ].astype(int)

    # ---------------------------------------------------------------
    # Numeric columns
    # ---------------------------------------------------------------

    clean_numeric_columns(
        pl,
        [
            "sales",
            "operating_profit",
            "net_profit",
            "eps",
        ],
    )

    clean_numeric_columns(
        bs,
        [
            "borrowings",
        ],
    )

    clean_numeric_columns(
        cf,
        [
            "operating_activity",
            "investing_activity",
            "financing_activity",
            "net_cash_flow",
        ],
    )

    # ---------------------------------------------------------------
    # Remove duplicate company/year rows
    # ---------------------------------------------------------------

    pl = (
        pl.sort_values(
            ["company_id", "year_num"]
        )
        .drop_duplicates(
            ["company_id", "year_num"],
            keep="first",
        )
    )

    bs = (
        bs.sort_values(
            ["company_id", "year_num"]
        )
        .drop_duplicates(
            ["company_id", "year_num"],
            keep="first",
        )
    )

    cf = (
        cf.sort_values(
            ["company_id", "year_num"]
        )
        .drop_duplicates(
            ["company_id", "year_num"],
            keep="first",
        )
    )

    # ---------------------------------------------------------------
    # Sector universe
    # ---------------------------------------------------------------

    sectors = sectors[
        [
            "company_id",
            "broad_sector",
        ]
    ].drop_duplicates(
        "company_id",
        keep="first",
    )

    # ---------------------------------------------------------------
    # MASTER UNIVERSE
    # ---------------------------------------------------------------

    company_ids = sorted(
        sectors["company_id"]
        .dropna()
        .unique()
        .tolist()
    )

    print(
        f"P&L annual rows : {len(pl)}"
    )

    print(
        f"BS annual rows  : {len(bs)}"
    )

    print(
        f"CF annual rows  : {len(cf)}"
    )

    print(
        f"Sector companies : {len(company_ids)}"
    )

    print()

    return (
        pl,
        bs,
        cf,
        sectors,
        company_ids,
    )


# =====================================================================
# FCF CAGR
# =====================================================================

def calculate_fcf_cagr_5yr(company_cf):

    if company_cf is None or company_cf.empty:
        return None

    data = company_cf[
        [
            "year_num",
            "free_cash_flow",
        ]
    ].dropna()

    if data.empty:
        return None

    data = data.sort_values(
        "year_num"
    )

    latest_year = int(
        data["year_num"].max()
    )

    target_start = latest_year - 5

    start_rows = data[
        data["year_num"] == target_start
    ]

    end_rows = data[
        data["year_num"] == latest_year
    ]

    if start_rows.empty or end_rows.empty:
        return None

    start_value = to_float(
        start_rows.iloc[-1][
            "free_cash_flow"
        ]
    )

    end_value = to_float(
        end_rows.iloc[-1][
            "free_cash_flow"
        ]
    )

    if (
        start_value is None
        or end_value is None
    ):
        return None

    # CAGR is not meaningful with zero/negative base.
    if start_value <= 0 or end_value <= 0:
        return None

    try:
        return (
            (
                end_value / start_value
            ) ** (1 / 5)
            - 1
        ) * 100

    except (
        ZeroDivisionError,
        ValueError,
    ):
        return None


# =====================================================================
# CFO QUALITY
# =====================================================================

def get_five_year_cfo_quality(
    company_cf,
    company_pl,
):

    if (
        company_cf is None
        or company_cf.empty
        or company_pl is None
        or company_pl.empty
    ):
        return None

    merged = company_cf.merge(
        company_pl[
            [
                "company_id",
                "year_num",
                "net_profit",
            ]
        ],
        on=[
            "company_id",
            "year_num",
        ],
        how="inner",
    )

    if merged.empty:
        return None

    merged = (
        merged
        .sort_values("year_num")
        .tail(5)
    )

    cfo_values = merged[
        "operating_activity"
    ].tolist()

    pat_values = merged[
        "net_profit"
    ].tolist()

    return calculate_cfo_quality_score(
        cfo_values,
        pat_values,
    )


# =====================================================================
# DISTRESS
# =====================================================================

def distress_flag(latest_cf):

    if latest_cf is None:
        return False

    cfo = to_float(
        latest_cf.get(
            "operating_activity"
        )
    )

    cff = to_float(
        latest_cf.get(
            "financing_activity"
        )
    )

    if cfo is None or cff is None:
        return False

    return (
        cfo < 0
        and cff > 0
    )


# =====================================================================
# DELEVERAGING
# =====================================================================

def deleveraging_flag(
    latest_cf,
    latest_bs,
    previous_bs,
):

    if (
        latest_cf is None
        or latest_bs is None
        or previous_bs is None
    ):
        return False

    cff = to_float(
        latest_cf.get(
            "financing_activity"
        )
    )

    latest_debt = to_float(
        latest_bs.get(
            "borrowings"
        )
    )

    previous_debt = to_float(
        previous_bs.get(
            "borrowings"
        )
    )

    if (
        cff is None
        or latest_debt is None
        or previous_debt is None
    ):
        return False

    return (
        cff < 0
        and latest_debt < previous_debt
    )


# =====================================================================
# COMPANY RECORD
# =====================================================================

def build_company_record(
    company_id,
    sector,
    company_cf,
    company_pl,
    company_bs,
):

    # ---------------------------------------------------------------
    # Sort available sources.
    # ---------------------------------------------------------------

    if company_cf is not None:
        company_cf = company_cf.sort_values(
            "year_num"
        ).copy()

    if company_pl is not None:
        company_pl = company_pl.sort_values(
            "year_num"
        ).copy()

    if company_bs is not None:
        company_bs = company_bs.sort_values(
            "year_num"
        ).copy()

    # ---------------------------------------------------------------
    # Latest annual year.
    #
    # Prefer CF because the intelligence module is CF-focused.
    # Fall back to P&L, then BS.
    # ---------------------------------------------------------------

    available_years = []

    if (
        company_cf is not None
        and not company_cf.empty
    ):
        available_years.extend(
            company_cf[
                "year_num"
            ].tolist()
        )

    if (
        company_pl is not None
        and not company_pl.empty
    ):
        available_years.extend(
            company_pl[
                "year_num"
            ].tolist()
        )

    if (
        company_bs is not None
        and not company_bs.empty
    ):
        available_years.extend(
            company_bs[
                "year_num"
            ].tolist()
        )

    if not available_years:
        return {
            "company_id": company_id,
            "sector": sector,
            "cfo_quality_score": None,
            "cfo_quality_label": None,
            "capex_intensity_pct": None,
            "capex_label": None,
            "fcf_cagr_5yr": None,
            "fcf_conversion_pct": None,
            "distress_flag": False,
            "deleveraging_flag": False,
            "capital_allocation_label": None,
        }

    latest_year = max(
        available_years
    )

    # ---------------------------------------------------------------
    # Latest CF
    # ---------------------------------------------------------------

    latest_cf = None

    if (
        company_cf is not None
        and not company_cf.empty
    ):

        rows = company_cf[
            company_cf["year_num"]
            == latest_year
        ]

        if not rows.empty:
            latest_cf = (
                rows.iloc[-1]
                .to_dict()
            )

    # ---------------------------------------------------------------
    # Latest P&L
    # ---------------------------------------------------------------

    latest_pl = None

    if (
        company_pl is not None
        and not company_pl.empty
    ):

        rows = company_pl[
            company_pl["year_num"]
            == latest_year
        ]

        if not rows.empty:
            latest_pl = (
                rows.iloc[-1]
                .to_dict()
            )

    # ---------------------------------------------------------------
    # Latest BS
    # ---------------------------------------------------------------

    latest_bs = None

    if (
        company_bs is not None
        and not company_bs.empty
    ):

        rows = company_bs[
            company_bs["year_num"]
            == latest_year
        ]

        if not rows.empty:
            latest_bs = (
                rows.iloc[-1]
                .to_dict()
            )

    # ---------------------------------------------------------------
    # Previous BS for deleveraging.
    # ---------------------------------------------------------------

    previous_bs = None

    if (
        company_bs is not None
        and not company_bs.empty
    ):

        rows = company_bs[
            company_bs["year_num"]
            < latest_year
        ]

        if not rows.empty:
            previous_bs = (
                rows
                .sort_values("year_num")
                .iloc[-1]
                .to_dict()
            )

    # ---------------------------------------------------------------
    # Historical FCF
    # ---------------------------------------------------------------

    fcf_company = None

    if (
        company_cf is not None
        and not company_cf.empty
    ):

        fcf_company = company_cf.copy()

        fcf_company[
            "free_cash_flow"
        ] = fcf_company.apply(
            lambda row: free_cash_flow(
                row[
                    "operating_activity"
                ],
                row[
                    "investing_activity"
                ],
            ),
            axis=1,
        )

    # ---------------------------------------------------------------
    # CFO Quality
    # ---------------------------------------------------------------

    cfo_quality = (
        get_five_year_cfo_quality(
            company_cf,
            company_pl,
        )
    )

    cfo_label = classify_cfo_quality(
        cfo_quality
    )

    # ---------------------------------------------------------------
    # CapEx Intensity
    # ---------------------------------------------------------------

    capex_value = None

    if (
        latest_cf is not None
        and latest_pl is not None
    ):

        capex_value = capex_intensity(
            latest_cf.get(
                "investing_activity"
            ),
            latest_pl.get(
                "sales"
            ),
        )

    capex_label = (
        classify_capex_intensity(
            capex_value
        )
    )

    # ---------------------------------------------------------------
    # FCF CAGR
    # ---------------------------------------------------------------

    fcf_cagr = (
        calculate_fcf_cagr_5yr(
            fcf_company
        )
        if fcf_company is not None
        else None
    )

    # ---------------------------------------------------------------
    # FCF Conversion
    # ---------------------------------------------------------------

    fcf_conversion = None

    if (
        latest_cf is not None
        and latest_pl is not None
    ):

        latest_fcf = free_cash_flow(
            latest_cf.get(
                "operating_activity"
            ),
            latest_cf.get(
                "investing_activity"
            ),
        )

        fcf_conversion = (
            fcf_conversion_rate(
                latest_fcf,
                latest_pl.get(
                    "operating_profit"
                ),
            )
        )

    # ---------------------------------------------------------------
    # Distress
    # ---------------------------------------------------------------

    is_distress = distress_flag(
        latest_cf
    )

    # ---------------------------------------------------------------
    # Deleveraging
    # ---------------------------------------------------------------

    is_deleveraging = (
        deleveraging_flag(
            latest_cf,
            latest_bs,
            previous_bs,
        )
    )

    # ---------------------------------------------------------------
    # Capital allocation
    # ---------------------------------------------------------------

    allocation = None

    if latest_cf is not None:

        latest_cfo_pat = None

        if latest_pl is not None:

            latest_cfo_pat = (
                cfo_pat_ratio(
                    latest_cf.get(
                        "operating_activity"
                    ),
                    latest_pl.get(
                        "net_profit"
                    ),
                )
            )

        allocation = (
            capital_allocation_pattern(
                latest_cf.get(
                    "operating_activity"
                ),
                latest_cf.get(
                    "investing_activity"
                ),
                latest_cf.get(
                    "financing_activity"
                ),
                latest_cfo_pat,
            )
        )

    return {
        "company_id": company_id,
        "sector": sector,
        "cfo_quality_score": cfo_quality,
        "cfo_quality_label": cfo_label,
        "capex_intensity_pct": capex_value,
        "capex_label": capex_label,
        "fcf_cagr_5yr": fcf_cagr,
        "fcf_conversion_pct": fcf_conversion,
        "distress_flag": bool(
            is_distress
        ),
        "deleveraging_flag": bool(
            is_deleveraging
        ),
        "capital_allocation_label": allocation,
    }


# =====================================================================
# MAIN
# =====================================================================

def main():

    print()
    print("=" * 70)
    print("SPRINT 5 - DAY 31")
    print("CASH FLOW INTELLIGENCE")
    print("=" * 70)
    print()

    (
        pl,
        bs,
        cf,
        sectors,
        company_ids,
    ) = load_sources()

    sector_map = dict(
        zip(
            sectors[
                "company_id"
            ],
            sectors[
                "broad_sector"
            ],
        )
    )

    records = []

    for company_id in company_ids:

        company_cf = cf[
            cf["company_id"]
            == company_id
        ].copy()

        company_pl = pl[
            pl["company_id"]
            == company_id
        ].copy()

        company_bs = bs[
            bs["company_id"]
            == company_id
        ].copy()

        record = build_company_record(
            company_id,
            sector_map.get(
                company_id,
                "Unknown",
            ),
            company_cf,
            company_pl,
            company_bs,
        )

        records.append(record)

    result = pd.DataFrame(
        records
    )

    columns = [
        "company_id",
        "sector",
        "cfo_quality_score",
        "cfo_quality_label",
        "capex_intensity_pct",
        "capex_label",
        "fcf_cagr_5yr",
        "fcf_conversion_pct",
        "distress_flag",
        "deleveraging_flag",
        "capital_allocation_label",
    ]

    result = result[
        columns
    ]

    result = (
        result
        .sort_values("company_id")
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------------
    # Save Excel
    # ---------------------------------------------------------------

    excel_path = (
        OUTPUT
        / "cashflow_intelligence.xlsx"
    )

    result.to_excel(
        excel_path,
        index=False,
    )

    # ---------------------------------------------------------------
    # Distress alerts
    # ---------------------------------------------------------------

    distress_records = []

    for company_id in result.loc[
        result[
            "distress_flag"
        ],
        "company_id",
    ]:

        company_cf = cf[
            cf["company_id"]
            == company_id
        ].sort_values(
            "year_num"
        )

        company_pl = pl[
            pl["company_id"]
            == company_id
        ].sort_values(
            "year_num"
        )

        if company_cf.empty:
            continue

        latest_cf = (
            company_cf.iloc[-1]
        )

        latest_year = int(
            latest_cf["year_num"]
        )

        pl_rows = company_pl[
            company_pl["year_num"]
            == latest_year
        ]

        latest_pat = (
            pl_rows.iloc[-1][
                "net_profit"
            ]
            if not pl_rows.empty
            else None
        )

        distress_records.append(
            {
                "company_id": company_id,
                "year": latest_year,
                "cfo": latest_cf[
                    "operating_activity"
                ],
                "cff": latest_cf[
                    "financing_activity"
                ],
                "latest_net_profit": latest_pat,
            }
        )

    distress_df = pd.DataFrame(
        distress_records,
        columns=[
            "company_id",
            "year",
            "cfo",
            "cff",
            "latest_net_profit",
        ],
    )

    distress_path = (
        OUTPUT
        / "distress_alerts.csv"
    )

    distress_df.to_csv(
        distress_path,
        index=False,
    )

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------

    print("=" * 70)
    print("DAY 31 RESULTS")
    print("=" * 70)

    print(
        f"Companies processed : "
        f"{len(result)}"
    )

    print(
        f"Excel rows          : "
        f"{len(result)}"
    )

    print(
        f"Distress companies  : "
        f"{int(result['distress_flag'].sum())}"
    )

    print(
        f"Deleveraging        : "
        f"{int(result['deleveraging_flag'].sum())}"
    )

    print()

    print("CFO QUALITY:")

    print(
        result[
            "cfo_quality_label"
        ].value_counts(
            dropna=False
        )
    )

    print()

    print("CAPEX INTENSITY:")

    print(
        result[
            "capex_label"
        ].value_counts(
            dropna=False
        )
    )

    print()

    print("CAPITAL ALLOCATION:")

    print(
        result[
            "capital_allocation_label"
        ].value_counts(
            dropna=False
        )
    )

    print()

    print(
        f"Created: {excel_path}"
    )

    print(
        f"Created: {distress_path}"
    )

    print()

    # ---------------------------------------------------------------
    # HARD VALIDATION
    # ---------------------------------------------------------------

    required = {
        "company_id",
        "sector",
        "cfo_quality_score",
        "cfo_quality_label",
        "capex_intensity_pct",
        "capex_label",
        "fcf_cagr_5yr",
        "fcf_conversion_pct",
        "distress_flag",
        "deleveraging_flag",
        "capital_allocation_label",
    }

    missing_columns = (
        required
        - set(result.columns)
    )

    if missing_columns:
        raise AssertionError(
            f"Missing columns: "
            f"{missing_columns}"
        )

    if result[
        "company_id"
    ].duplicated().any():

        raise AssertionError(
            "Duplicate company IDs found."
        )

    if len(result) != 92:

        raise AssertionError(
            f"Expected 92 companies, "
            f"got {len(result)}."
        )

    print(
        "VALIDATION: PASS - "
        "92 unique companies"
    )

    # ---------------------------------------------------------------
    # Missing-data transparency
    # ---------------------------------------------------------------

    print()
    print("MISSING SOURCE COVERAGE:")

    for column in columns:

        missing = int(
            result[column]
            .isna()
            .sum()
        )

        if missing:
            print(
                f"{column}: "
                f"{missing} unavailable"
            )

    print()


if __name__ == "__main__":
    main()