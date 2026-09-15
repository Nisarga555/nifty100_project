"""
Sprint 5 - Day 32
Capital Allocation Pattern Analysis

Verifies:
    - Sprint 2 capital_allocation.csv coverage
    - 92-company coverage
    - All available annual years
    - Latest-year distribution across capital allocation patterns
    - YoY pattern changes

Output:
    output/pattern_changes.csv
"""

from pathlib import Path

import pandas as pd


# =====================================================================
# PATHS
# =====================================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT
    / "output"
    / "capital_allocation.csv"
)

OUTPUT_DIR = ROOT / "output"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "pattern_changes.csv"
)


# =====================================================================
# HELPERS
# =====================================================================

def normalize_company_id(value):
    if value is None:
        return None

    text = str(value).strip().upper()

    if not text or text == "NAN":
        return None

    return text


def normalize_year(value):
    """
    Normalize common annual year formats.

    Examples:
        Mar 2024 -> 2024
        Mar-24   -> 2024
        2024     -> 2024
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # Already numeric year.
    try:
        numeric = int(float(text))

        if 1900 <= numeric <= 2100:
            return numeric

    except (TypeError, ValueError):
        pass

    import re

    match = re.search(
        r"(20\d{2})",
        text,
    )

    if match:
        return int(match.group(1))

    match = re.search(
        r"(?:-| )(\d{2})$",
        text,
    )

    if match:
        yy = int(match.group(1))

        return (
            1900 + yy
            if yy >= 50
            else 2000 + yy
        )

    return None


# =====================================================================
# LOAD
# =====================================================================

def load_capital_allocation():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Missing required file: "
            f"{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"Input rows: {len(df)}"
    )

    print(
        "Input columns:"
    )

    print(
        list(df.columns)
    )

    return df


# =====================================================================
# STANDARDIZE
# =====================================================================

def standardize(df):

    df = df.copy()

    # ---------------------------------------------------------------
    # Company ID
    # ---------------------------------------------------------------

    if "company_id" not in df.columns:

        raise AssertionError(
            "capital_allocation.csv "
            "must contain company_id."
        )

    df["company_id"] = (
        df["company_id"]
        .apply(normalize_company_id)
    )

    # ---------------------------------------------------------------
    # Year
    # ---------------------------------------------------------------

    if "year" not in df.columns:

        raise AssertionError(
            "capital_allocation.csv "
            "must contain year."
        )

    df["year_num"] = (
        df["year"]
        .apply(normalize_year)
    )

    # ---------------------------------------------------------------
    # Pattern column
    # ---------------------------------------------------------------

    pattern_column = None

    for candidate in [
        "pattern_label",
        "capital_allocation_pattern",
        "capital_allocation_label",
    ]:

        if candidate in df.columns:

            pattern_column = candidate
            break

    if pattern_column is None:

        raise AssertionError(
            "Could not find capital "
            "allocation pattern column."
        )

    df["pattern"] = (
        df[pattern_column]
        .astype(str)
        .str.strip()
    )

    df.loc[
        df["pattern"].isin(
            ["", "None", "nan", "NaN"]
        ),
        "pattern",
    ] = pd.NA

    # ---------------------------------------------------------------
    # Remove unusable records
    # ---------------------------------------------------------------

    df = df[
        df["company_id"].notna()
        & df["year_num"].notna()
        & df["pattern"].notna()
    ].copy()

    df["year_num"] = (
        df["year_num"]
        .astype(int)
    )

    # ---------------------------------------------------------------
    # Remove duplicate company/year rows
    # ---------------------------------------------------------------

    duplicates = df.duplicated(
        [
            "company_id",
            "year_num",
        ],
        keep=False,
    )

    duplicate_count = int(
        duplicates.sum()
    )

    if duplicate_count:

        print(
            f"WARNING: {duplicate_count} "
            "duplicate company-year rows."
        )

        df = (
            df.sort_values(
                [
                    "company_id",
                    "year_num",
                ]
            )
            .drop_duplicates(
                [
                    "company_id",
                    "year_num",
                ],
                keep="first",
            )
        )

    return df


# =====================================================================
# COVERAGE VALIDATION
# =====================================================================

def validate_coverage(df):

    company_count = (
        df["company_id"]
        .nunique()
    )

    year_count = (
        df["year_num"]
        .nunique()
    )

    print()
    print("=" * 70)
    print("CAPITAL ALLOCATION COVERAGE")
    print("=" * 70)

    print(
        f"Unique companies : {company_count}"
    )

    print(
        f"Available years  : {year_count}"
    )

    print(
        f"Company-year rows: {len(df)}"
    )

    years = sorted(
        df["year_num"]
        .unique()
    )

    print(
        f"Years: {years}"
    )

    if company_count != 92:

        raise AssertionError(
            f"Expected 92 companies, "
            f"found {company_count}."
        )

    # ---------------------------------------------------------------
    # Expected complete coverage means each company should have
    # the same set of available years represented in the source.
    # ---------------------------------------------------------------

    coverage = (
        df.groupby(
            "company_id"
        )["year_num"]
        .nunique()
    )

    print()
    print(
        "Rows per company:"
    )

    print(
        coverage.value_counts()
        .sort_index()
        .to_string()
    )

    # ---------------------------------------------------------------
    # Find companies with unusually low coverage.
    # ---------------------------------------------------------------

    minimum_years = int(
        coverage.min()
    )

    companies_with_minimum = sorted(
        coverage[
            coverage == minimum_years
        ].index
        .tolist()
    )

    print()
    print(
        f"Minimum years/company: "
        f"{minimum_years}"
    )

    if minimum_years < 3:

        print(
            "WARNING: Some companies "
            "have fewer than 3 annual "
            "records."
        )

        print(
            companies_with_minimum
        )

    return years


# =====================================================================
# LATEST-YEAR DISTRIBUTION
# =====================================================================

def latest_distribution(df):

    latest_year = int(
        df["year_num"].max()
    )

    latest = df[
        df["year_num"]
        == latest_year
    ].copy()

    distribution = (
        latest["pattern"]
        .value_counts()
        .sort_index()
    )

    print()
    print("=" * 70)
    print(
        f"LATEST-YEAR PATTERN DISTRIBUTION "
        f"({latest_year})"
    )
    print("=" * 70)

    print(
        distribution.to_string()
    )

    print()
    print(
        f"Latest-year company rows: "
        f"{len(latest)}"
    )

    return latest_year, latest, distribution


# =====================================================================
# YOY PATTERN CHANGES
# =====================================================================

def calculate_pattern_changes(df):

    print()
    print("=" * 70)
    print("CALCULATING YOY PATTERN CHANGES")
    print("=" * 70)

    data = df[
        [
            "company_id",
            "year_num",
            "pattern",
        ]
    ].copy()

    data = data.sort_values(
        [
            "company_id",
            "year_num",
        ]
    )

    # ---------------------------------------------------------------
    # Previous year's pattern
    # ---------------------------------------------------------------

    data["previous_pattern"] = (
        data
        .groupby("company_id")[
            "pattern"
        ]
        .shift(1)
    )

    data["previous_year"] = (
        data
        .groupby("company_id")[
            "year_num"
        ]
        .shift(1)
    )

    # ---------------------------------------------------------------
    # Only compare consecutive annual years.
    # ---------------------------------------------------------------

    data["is_consecutive"] = (
        data["previous_year"].notna()
        & (
            data["year_num"]
            - data["previous_year"]
            == 1
        )
    )

    changes = data[
        data["is_consecutive"]
    ].copy()

    # ---------------------------------------------------------------
    # Only genuine changes.
    # ---------------------------------------------------------------

    changes = changes[
        changes["pattern"]
        != changes["previous_pattern"]
    ].copy()

    changes["change_type"] = (
        changes["previous_pattern"]
        + " -> "
        + changes["pattern"]
    )

    # ---------------------------------------------------------------
    # Final columns
    # ---------------------------------------------------------------

    changes = changes[
        [
            "company_id",
            "previous_year",
            "year_num",
            "previous_pattern",
            "pattern",
            "change_type",
        ]
    ].rename(
        columns={
            "previous_year": "from_year",
            "year_num": "to_year",
            "previous_pattern":
                "previous_pattern",
            "pattern":
                "current_pattern",
        }
    )

    changes = (
        changes
        .sort_values(
            [
                "company_id",
                "to_year",
            ]
        )
        .reset_index(drop=True)
    )

    return changes


# =====================================================================
# MAIN
# =====================================================================

def main():

    print()
    print("=" * 70)
    print("SPRINT 5 - DAY 32")
    print("CAPITAL ALLOCATION PATTERN ANALYSIS")
    print("=" * 70)
    print()

    # ---------------------------------------------------------------
    # Load
    # ---------------------------------------------------------------

    raw = load_capital_allocation()

    # ---------------------------------------------------------------
    # Standardize
    # ---------------------------------------------------------------

    df = standardize(
        raw
    )

    # ---------------------------------------------------------------
    # Coverage
    # ---------------------------------------------------------------

    years = validate_coverage(
        df
    )

    # ---------------------------------------------------------------
    # Latest distribution
    # ---------------------------------------------------------------

    latest_year, latest, distribution = (
        latest_distribution(df)
    )

    # ---------------------------------------------------------------
    # YoY changes
    # ---------------------------------------------------------------

    changes = (
        calculate_pattern_changes(df)
    )

    # ---------------------------------------------------------------
    # Save
    # ---------------------------------------------------------------

    changes.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------

    print()
    print("=" * 70)
    print("DAY 32 RESULTS")
    print("=" * 70)

    print(
        f"Companies covered : "
        f"{df['company_id'].nunique()}"
    )

    print(
        f"Years covered     : "
        f"{len(years)}"
    )

    print(
        f"Company-year rows : "
        f"{len(df)}"
    )

    print(
        f"Latest year       : "
        f"{latest_year}"
    )

    print(
        f"Latest-year rows  : "
        f"{len(latest)}"
    )

    print(
        f"Pattern changes   : "
        f"{len(changes)}"
    )

    print()
    print(
        "Latest-year distribution:"
    )

    print(
        distribution.to_string()
    )

    print()
    print(
        "Most common YoY transitions:"
    )

    if changes.empty:

        print(
            "No pattern changes detected."
        )

    else:

        transitions = (
            changes[
                "change_type"
            ]
            .value_counts()
            .head(15)
        )

        print(
            transitions.to_string()
        )

    print()
    print(
        f"Created: {OUTPUT_FILE}"
    )

    # ---------------------------------------------------------------
    # HARD VALIDATION
    # ---------------------------------------------------------------

    required_columns = {
        "company_id",
        "from_year",
        "to_year",
        "previous_pattern",
        "current_pattern",
        "change_type",
    }

    if not required_columns.issubset(
        changes.columns
    ):

        raise AssertionError(
            "pattern_changes.csv "
            "is missing required columns."
        )

    if (
        df["company_id"]
        .nunique()
        != 92
    ):

        raise AssertionError(
            "Capital allocation does "
            "not cover all 92 companies."
        )

    if changes.duplicated(
        [
            "company_id",
            "to_year",
        ]
    ).any():

        raise AssertionError(
            "Duplicate company/year "
            "pattern changes found."
        )

    print()
    print(
        "VALIDATION: PASS"
    )

    print(
        "92 companies covered."
    )

    print(
        "YoY pattern changes generated."
    )

    print()


if __name__ == "__main__":
    main()