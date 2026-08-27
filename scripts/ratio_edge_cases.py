from pathlib import Path
import math
import sqlite3
from datetime import datetime

import pandas as pd

from src.etl.loader import load_all_sources


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "nifty100.sqlite3"
OUTPUT_DIR = BASE_DIR / "output"
LOG_PATH = OUTPUT_DIR / "ratio_edge_cases.log"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def safe_float(value):
    if value is None or pd.isna(value):
        return None

    try:
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def clean_key(value):
    if value is None or pd.isna(value):
        return None

    value = str(value).strip().upper()

    if not value or value == "NAN":
        return None

    return value


def year_sort_value(year):
    """
    Convert YYYY-MM / YYYY-MM-DD style values into
    a sortable integer.

    TTM is deliberately treated as older than a
    proper annual period so it will not be selected
    as the latest annual comparison period.
    """

    if year is None or pd.isna(year):
        return -1

    text = str(year).strip().upper()

    if text == "TTM":
        return -1

    try:
        parts = text.split("-")

        year_number = int(parts[0])

        month_number = 0

        if len(parts) >= 2:
            month_number = int(parts[1])

        return (
            year_number * 100
            + month_number
        )

    except (
        TypeError,
        ValueError
    ):
        return -1


def is_annual_period(year):
    """
    Accept normal YYYY-MM annual periods.

    Reject TTM and malformed periods.
    """

    if year is None or pd.isna(year):
        return False

    text = str(year).strip().upper()

    if text == "TTM":
        return False

    parts = text.split("-")

    if len(parts) != 2:
        return False

    try:
        int(parts[0])
        month = int(parts[1])

        return 1 <= month <= 12

    except (
        TypeError,
        ValueError
    ):
        return False


def classify_anomaly(
    computed,
    source
):
    computed = safe_float(
        computed
    )

    source = safe_float(
        source
    )

    if computed is None and source is None:
        return "DATA_SOURCE_ISSUE"

    if computed is None:
        return "DATA_SOURCE_ISSUE"

    if source is None:
        return "DATA_SOURCE_ISSUE"

    difference = abs(
        computed - source
    )

    if difference <= 10:
        return "VERSION_DIFFERENCE"

    return "FORMULA_DISCREPANCY"


def load_ratio_database():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    connection = sqlite3.connect(
        DB_PATH
    )

    try:

        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            ).fetchall()
        }

        if "financial_ratios" not in tables:
            raise RuntimeError(
                "financial_ratios table does not exist"
            )

        df = pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            ORDER BY company_id, year
            """,
            connection
        )

    finally:

        connection.close()

    return df


def build_company_lookup(
    companies
):
    lookup = {}

    if companies is None or companies.empty:
        return lookup

    for _, row in companies.iterrows():

        company_id = clean_key(
            row.get("id")
        )

        if company_id is None:
            continue

        lookup[company_id] = row.to_dict()

    return lookup


def build_sector_lookup(
    sectors
):
    lookup = {}

    if sectors is None or sectors.empty:
        return lookup

    for _, row in sectors.iterrows():

        company_id = clean_key(
            row.get("company_id")
        )

        if company_id is None:
            continue

        lookup[company_id] = row.to_dict()

    return lookup


def select_latest_annual_rows(
    ratios
):
    """
    Select ONE latest annual financial-ratio row
    per company.

    This is critical because companies.xlsx contains
    one ROE/ROCE source value per company rather than
    one value per historical year.
    """

    df = ratios.copy()

    df["company_id"] = (
        df["company_id"]
        .apply(clean_key)
    )

    df = df[
        df["company_id"].notna()
    ]

    df = df[
        df["year"].apply(
            is_annual_period
        )
    ]

    df["_year_sort"] = (
        df["year"]
        .apply(
            year_sort_value
        )
    )

    # Only rows where at least one of the
    # computed ratios exists are useful.
    df = df[
        df[
            [
                "return_on_equity_pct",
                "return_on_capital_employed_pct",
            ]
        ]
        .notna()
        .any(axis=1)
    ]

    df = (
        df.sort_values(
            [
                "company_id",
                "_year_sort",
            ]
        )
        .groupby(
            "company_id",
            as_index=False
        )
        .tail(1)
        .copy()
    )

    df = df.drop(
        columns=[
            "_year_sort"
        ],
        errors="ignore"
    )

    return df.reset_index(
        drop=True
    )


def write_anomaly(
    handle,
    row,
    ratio_name,
    computed,
    source,
    category
):
    computed_value = safe_float(
        computed
    )

    source_value = safe_float(
        source
    )

    if (
        computed_value is not None
        and source_value is not None
    ):
        difference = abs(
            computed_value
            - source_value
        )
    else:
        difference = None

    handle.write(
        "\n"
        + "-" * 80
        + "\n"
    )

    handle.write(
        f"Company ID       : "
        f"{row['company_id']}\n"
    )

    handle.write(
        f"Company Name     : "
        f"{row.get('company_name')}\n"
    )

    handle.write(
        f"Comparison Year  : "
        f"{row['year']}\n"
    )

    handle.write(
        f"Broad Sector     : "
        f"{row.get('broad_sector')}\n"
    )

    handle.write(
        f"Ratio            : "
        f"{ratio_name}\n"
    )

    handle.write(
        f"Computed Value   : "
        f"{computed_value}\n"
    )

    handle.write(
        f"Source Value     : "
        f"{source_value}\n"
    )

    handle.write(
        f"Absolute Diff.   : "
        f"{difference}\n"
    )

    handle.write(
        f"Category         : "
        f"{category}\n"
    )

    if category == "DATA_SOURCE_ISSUE":

        explanation = (
            "Source value is missing or invalid, "
            "or the computed value cannot be "
            "reconciled with available data."
        )

    elif category == "VERSION_DIFFERENCE":

        explanation = (
            "The difference is relatively small "
            "and may be explained by source-version, "
            "rounding, timing, or period differences."
        )

    else:

        explanation = (
            "The difference is material and may "
            "indicate a formula-definition or "
            "underlying-input difference. The "
            "ratio-engine value is retained for "
            "analytics."
        )

    handle.write(
        f"Explanation      : "
        f"{explanation}\n"
    )


def check_latest_ratio(
    latest_df,
    computed_column,
    source_column,
    ratio_name,
    handle
):
    anomalies = 0

    for _, row in latest_df.iterrows():

        computed = safe_float(
            row.get(
                computed_column
            )
        )

        source = safe_float(
            row.get(
                source_column
            )
        )

        if computed is None:
            continue

        if source is None:

            category = (
                "DATA_SOURCE_ISSUE"
            )

            write_anomaly(
                handle,
                row,
                ratio_name,
                computed,
                source,
                category
            )

            anomalies += 1
            continue

        difference = abs(
            computed - source
        )

        if difference > 5:

            category = (
                classify_anomaly(
                    computed,
                    source
                )
            )

            write_anomaly(
                handle,
                row,
                ratio_name,
                computed,
                source,
                category
            )

            anomalies += 1

    return anomalies


def check_financials_carveout(
    latest_df,
    handle
):
    handle.write(
        "\n"
        + "=" * 80
        + "\n"
    )

    handle.write(
        "FINANCIALS SECTOR D/E CARVE-OUT\n"
    )

    handle.write(
        "=" * 80
        + "\n"
    )

    if "broad_sector" not in latest_df.columns:

        handle.write(
            "[WARNING] broad_sector unavailable.\n"
        )

        return 0

    financials = latest_df[
        latest_df[
            "broad_sector"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        == "financials"
    ]

    handle.write(
        f"Financials companies checked: "
        f"{len(financials)}\n"
    )

    handle.write(
        "Standard D/E warning: SUPPRESSED\n"
    )

    handle.write(
        "Reason: high leverage is structurally "
        "normal for banks, NBFCs and insurance "
        "companies.\n"
    )

    companies = (
        financials[
            "company_id"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    if len(companies) > 0:

        handle.write(
            "Companies: "
            + ", ".join(
                sorted(companies)
            )
            + "\n"
        )

    return len(financials)


def main():

    print("=" * 70)
    print(
        "NIFTY 100 - DAY 13 RATIO EDGE-CASE AUDIT"
    )
    print("=" * 70)

    # ------------------------------------------------------------
    # Load ratio-engine database
    # ------------------------------------------------------------

    try:

        ratios = load_ratio_database()

    except Exception as exc:

        print(
            f"[ERROR] {exc}"
        )

        return 1

    print(
        f"[OK] financial_ratios rows: "
        f"{len(ratios)}"
    )

    # ------------------------------------------------------------
    # Load source data
    # ------------------------------------------------------------

    print(
        "[INFO] Loading source company data..."
    )

    try:

        datasets = load_all_sources()

    except Exception as exc:

        print(
            f"[ERROR] Could not load source data: "
            f"{exc}"
        )

        return 1

    companies = datasets.get(
        "companies",
        pd.DataFrame()
    )

    sectors = datasets.get(
        "sectors",
        pd.DataFrame()
    )

    print(
        f"[OK] Source companies: "
        f"{len(companies)}"
    )

    print(
        f"[OK] Source sectors: "
        f"{len(sectors)}"
    )

    # ------------------------------------------------------------
    # Build lookups
    # ------------------------------------------------------------

    company_lookup = (
        build_company_lookup(
            companies
        )
    )

    sector_lookup = (
        build_sector_lookup(
            sectors
        )
    )

    # ------------------------------------------------------------
    # Select latest annual row PER COMPANY
    # ------------------------------------------------------------

    latest = (
        select_latest_annual_rows(
            ratios
        )
    )

    source_roce = []
    source_roe = []
    company_names = []
    broad_sectors = []

    for _, row in latest.iterrows():

        company_id = clean_key(
            row["company_id"]
        )

        company = (
            company_lookup.get(
                company_id,
                {}
            )
        )

        sector = (
            sector_lookup.get(
                company_id,
                {}
            )
        )

        source_roce.append(
            safe_float(
                company.get(
                    "roce_percentage"
                )
            )
        )

        source_roe.append(
            safe_float(
                company.get(
                    "roe_percentage"
                )
            )
        )

        company_names.append(
            company.get(
                "company_name"
            )
        )

        broad_sectors.append(
            sector.get(
                "broad_sector"
            )
        )

    latest[
        "source_roce_percentage"
    ] = source_roce

    latest[
        "source_roe_percentage"
    ] = source_roe

    latest[
        "company_name"
    ] = company_names

    latest[
        "broad_sector"
    ] = broad_sectors

    print(
        f"[OK] Latest annual company rows: "
        f"{len(latest)}"
    )

    # ------------------------------------------------------------
    # Write log
    # ------------------------------------------------------------

    with open(
        LOG_PATH,
        "w",
        encoding="utf-8"
    ) as handle:

        handle.write(
            "=" * 80
            + "\n"
        )

        handle.write(
            "NIFTY 100 - RATIO ENGINE EDGE CASE LOG\n"
        )

        handle.write(
            "=" * 80
            + "\n"
        )

        handle.write(
            f"Generated: "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        handle.write(
            f"Total financial_ratios rows: "
            f"{len(ratios)}\n"
        )

        handle.write(
            f"Latest annual company rows audited: "
            f"{len(latest)}\n"
        )

        handle.write(
            "\n"
        )

        handle.write(
            "IMPORTANT COMPARISON RULE:\n"
        )

        handle.write(
            "companies.xlsx contains one company-level "
            "ROE/ROCE source value without a year column.\n"
        )

        handle.write(
            "Therefore the source values are compared "
            "ONLY against the latest available annual "
            "company-year ratio-engine value.\n"
        )

        handle.write(
            "Historical company-year rows are NOT "
            "treated as anomalies.\n"
        )

        handle.write(
            "\n"
        )

        handle.write(
            "Anomaly threshold: > 5 percentage points\n"
        )

        # --------------------------------------------------------
        # ROCE
        # --------------------------------------------------------

        handle.write(
            "\n"
            + "=" * 80
            + "\n"
        )

        handle.write(
            "ROCE CROSS-CHECK\n"
        )

        handle.write(
            "=" * 80
            + "\n"
        )

        roce_anomalies = (
            check_latest_ratio(
                latest,
                "return_on_capital_employed_pct",
                "source_roce_percentage",
                "ROCE",
                handle
            )
        )

        handle.write(
            f"\nROCE anomalies found: "
            f"{roce_anomalies}\n"
        )

        # --------------------------------------------------------
        # ROE
        # --------------------------------------------------------

        handle.write(
            "\n"
            + "=" * 80
            + "\n"
        )

        handle.write(
            "ROE CROSS-CHECK\n"
        )

        handle.write(
            "=" * 80
            + "\n"
        )

        roe_anomalies = (
            check_latest_ratio(
                latest,
                "return_on_equity_pct",
                "source_roe_percentage",
                "ROE",
                handle
            )
        )

        handle.write(
            f"\nROE anomalies found: "
            f"{roe_anomalies}\n"
        )

        # --------------------------------------------------------
        # Financials carve-out
        # --------------------------------------------------------

        financials_rows = (
            check_financials_carveout(
                latest,
                handle
            )
        )

        # --------------------------------------------------------
        # Summary
        # --------------------------------------------------------

        total_anomalies = (
            roce_anomalies
            + roe_anomalies
        )

        handle.write(
            "\n"
            + "=" * 80
            + "\n"
        )

        handle.write(
            "FINAL SUMMARY\n"
        )

        handle.write(
            "=" * 80
            + "\n"
        )

        handle.write(
            f"Ratio rows audited          : "
            f"{len(ratios)}\n"
        )

        handle.write(
            f"Companies audited           : "
            f"{len(latest)}\n"
        )

        handle.write(
            f"ROCE anomalies              : "
            f"{roce_anomalies}\n"
        )

        handle.write(
            f"ROE anomalies               : "
            f"{roe_anomalies}\n"
        )

        handle.write(
            f"Total anomalies             : "
            f"{total_anomalies}\n"
        )

        handle.write(
            f"Financials rows checked     : "
            f"{financials_rows}\n"
        )

        handle.write(
            "\n"
        )

        handle.write(
            "Categories:\n"
        )

        handle.write(
            "DATA_SOURCE_ISSUE\n"
        )

        handle.write(
            "VERSION_DIFFERENCE\n"
        )

        handle.write(
            "FORMULA_DISCREPANCY\n"
        )

        handle.write(
            "\n"
        )

        handle.write(
            "Day-13 ratio edge-case audit completed.\n"
        )

    print()
    print(
        f"[OK] Latest annual rows audited: "
        f"{len(latest)}"
    )

    print(
        f"[OK] ROCE anomalies: "
        f"{roce_anomalies}"
    )

    print(
        f"[OK] ROE anomalies: "
        f"{roe_anomalies}"
    )

    print(
        f"[OK] Financials rows checked: "
        f"{financials_rows}"
    )

    print(
        f"[OK] Total anomalies: "
        f"{total_anomalies}"
    )

    print(
        "[OK] ratio_edge_cases.log created:"
    )

    print(
        f"     {LOG_PATH}"
    )

    print()
    print("=" * 70)
    print(
        "DAY 13 EDGE-CASE AUDIT COMPLETE"
    )
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )