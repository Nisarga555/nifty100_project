from pathlib import Path

import pandas as pd

from src.etl.loader import load_all_sources


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def add_failure(
    failures,
    rule_id,
    severity,
    table_name,
    message,
    company_id=None,
    year=None,
):
    """Add one validation failure."""

    failures.append(
        {
            "rule_id": rule_id,
            "severity": severity,
            "table_name": table_name,
            "company_id": company_id,
            "year": year,
            "message": message,
        }
    )


# -------------------------------------------------------------------
# DQ-01 — Primary Key Uniqueness
# -------------------------------------------------------------------

def validate_pk_uniqueness(datasets, failures):
    """
    DQ-01:
    Every table's id column must contain unique values.
    """

    for table_name, df in datasets.items():

        if "id" not in df.columns:
            continue

        duplicates = df[
            df["id"].duplicated(keep=False)
        ]

        for _, row in duplicates.iterrows():

            add_failure(
                failures,
                "DQ-01",
                "CRITICAL",
                table_name,
                f"Duplicate primary key: {row['id']}",
            )


# -------------------------------------------------------------------
# DQ-02 — Company + Year Uniqueness
# -------------------------------------------------------------------

def validate_company_year_uniqueness(datasets, failures):
    """
    DQ-02:
    company_id + year must be unique for annual financial tables.
    """

    tables = [
        "profitandloss",
        "balancesheet",
        "cashflow",
        "documents",
        "financial_ratios",
        "market_cap",
    ]

    for table_name in tables:

        if table_name not in datasets:
            continue

        df = datasets[table_name]

        if not {
            "company_id",
            "year",
        }.issubset(df.columns):
            continue

        duplicates = df[
            df.duplicated(
                subset=[
                    "company_id",
                    "year",
                ],
                keep=False,
            )
        ]

        for _, row in duplicates.iterrows():

            add_failure(
                failures,
                "DQ-02",
                "CRITICAL",
                table_name,
                "Duplicate company_id + year combination",
                row["company_id"],
                row["year"],
            )


# -------------------------------------------------------------------
# DQ-03 — Foreign Key Integrity
# -------------------------------------------------------------------

def validate_foreign_keys(datasets, failures):
    """
    DQ-03:
    Every company_id must exist in companies.id.
    """

    companies = datasets["companies"]

    valid_company_ids = set(
        companies["id"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for table_name, df in datasets.items():

        if "company_id" not in df.columns:
            continue

        company_ids = (
            df["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        invalid = df[
            df["company_id"].notna()
            & ~company_ids.isin(
                valid_company_ids
            )
        ]

        for _, row in invalid.iterrows():

            add_failure(
                failures,
                "DQ-03",
                "CRITICAL",
                table_name,
                f"Unknown company_id: {row['company_id']}",
                row["company_id"],
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-04 — Balance Sheet Balance
# -------------------------------------------------------------------

def validate_balance_sheet(datasets, failures):
    """
    DQ-04:
    Assets and liabilities should balance within 1%.
    """

    if "balancesheet" not in datasets:
        return

    df = datasets["balancesheet"]

    for _, row in df.iterrows():

        assets = row.get("total_assets")
        liabilities = row.get(
            "total_liabilities"
        )

        if pd.isna(assets):
            continue

        if pd.isna(liabilities):
            continue

        if assets == 0:
            continue

        difference = (
            abs(assets - liabilities)
            / abs(assets)
        )

        if difference >= 0.01:

            add_failure(
                failures,
                "DQ-04",
                "CRITICAL",
                "balancesheet",
                (
                    "Assets/liabilities imbalance: "
                    f"{difference:.2%}"
                ),
                row.get("company_id"),
                row.get("year"),
            )


# -------------------------------------------------------------------
# DQ-05 — OPM Cross Check
# -------------------------------------------------------------------

def validate_opm(datasets, failures):
    """
    DQ-05:
    Validate reported Operating Profit Margin.

    Calculated OPM:

        operating_profit / sales * 100

    Classification:

        difference <= 1%
            PASS

        1% < difference <= 5%
            WARNING

        difference > 5%
            CRITICAL

    Reported OPM values above 100% are not automatically failures.
    The reported value is compared with the calculated value first.
    """

    if "profitandloss" not in datasets:
        return

    df = datasets["profitandloss"]

    required_columns = {
        "company_id",
        "year",
        "sales",
        "operating_profit",
        "opm_percentage",
    }

    if not required_columns.issubset(
        df.columns
    ):
        return

    for _, row in df.iterrows():

        sales = row["sales"]
        operating_profit = row[
            "operating_profit"
        ]
        reported_opm = row[
            "opm_percentage"
        ]

        if pd.isna(sales):
            continue

        if sales == 0:
            continue

        if pd.isna(operating_profit):
            continue

        if pd.isna(reported_opm):
            continue

        calculated_opm = (
            operating_profit / sales
        ) * 100

        difference = abs(
            reported_opm - calculated_opm
        )

        # -----------------------------------------------------------
        # PASS
        # -----------------------------------------------------------

        if difference <= 1:
            continue

        # -----------------------------------------------------------
        # WARNING
        # -----------------------------------------------------------

        if difference <= 5:

            message = (
                "OPM minor mismatch: "
                f"reported={reported_opm}, "
                f"calculated={calculated_opm:.2f}, "
                f"difference={difference:.2f}"
            )

            add_failure(
                failures,
                "DQ-05",
                "WARNING",
                "profitandloss",
                message,
                row["company_id"],
                row["year"],
            )

            continue

        # -----------------------------------------------------------
        # CRITICAL
        # -----------------------------------------------------------

        message = (
            "OPM major mismatch: "
            f"reported={reported_opm}, "
            f"calculated={calculated_opm:.2f}, "
            f"difference={difference:.2f}"
        )

        if abs(reported_opm) > 100:
            message += (
                " | reported OPM exceeds 100%"
            )

        add_failure(
            failures,
            "DQ-05",
            "CRITICAL",
            "profitandloss",
            message,
            row["company_id"],
            row["year"],
        )


# -------------------------------------------------------------------
# DQ-06 — Positive Sales
# -------------------------------------------------------------------

def validate_positive_sales(datasets, failures):
    """
    DQ-06:
    Validate sales values.

    Rules:

        sales > 0
            PASS

        sales == 0 and operating_profit == 0
            PASS

        sales == 0 and operating_profit != 0
            WARNING

        sales < 0
            WARNING

    A zero-sales and zero-operating-profit record represents a
    period where OPM is undefined (0 / 0), so it is not treated
    as an error.
    """

    if "profitandloss" not in datasets:
        return

    df = datasets["profitandloss"]

    required_columns = {
        "company_id",
        "year",
        "sales",
        "operating_profit",
    }

    if not required_columns.issubset(
        df.columns
    ):
        return

    for _, row in df.iterrows():

        sales = row["sales"]
        operating_profit = row[
            "operating_profit"
        ]

        # -----------------------------------------------------------
        # Missing sales
        # -----------------------------------------------------------

        if pd.isna(sales):
            continue

        # -----------------------------------------------------------
        # Positive sales
        # -----------------------------------------------------------

        if sales > 0:
            continue

        # -----------------------------------------------------------
        # Zero sales + zero operating profit
        #
        # Example:
        # ADANIENSOL 2014-03
        # sales = 0
        # operating_profit = 0
        #
        # OPM = 0 / 0, which is undefined.
        # This is therefore ignored rather than reported as a
        # data-quality failure.
        # -----------------------------------------------------------

        if (
            sales == 0
            and not pd.isna(
                operating_profit
            )
            and operating_profit == 0
        ):
            continue

        # -----------------------------------------------------------
        # Zero sales + non-zero operating profit
        # -----------------------------------------------------------

        if sales == 0:

            add_failure(
                failures,
                "DQ-06",
                "WARNING",
                "profitandloss",
                (
                    "Zero sales with non-zero "
                    "operating profit: "
                    f"sales={sales}, "
                    f"operating_profit="
                    f"{operating_profit}"
                ),
                row["company_id"],
                row["year"],
            )

            continue

        # -----------------------------------------------------------
        # Negative sales
        # -----------------------------------------------------------

        add_failure(
            failures,
            "DQ-06",
            "WARNING",
            "profitandloss",
            f"Negative sales: {sales}",
            row["company_id"],
            row["year"],
        )


# -------------------------------------------------------------------
# DQ-07 — Net Cash
# -------------------------------------------------------------------

def validate_net_cash(datasets, failures):
    """
    DQ-07:
    Net cash flow should equal:

        operating + investing + financing
    """

    if "cashflow" not in datasets:
        return

    df = datasets["cashflow"]

    required_columns = {
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
        "financing_activity",
        "net_cash_flow",
    }

    if not required_columns.issubset(
        df.columns
    ):
        return

    for _, row in df.iterrows():

        components = [
            row["operating_activity"],
            row["investing_activity"],
            row["financing_activity"],
        ]

        reported = row[
            "net_cash_flow"
        ]

        if any(
            pd.isna(value)
            for value in components
        ):
            continue

        if pd.isna(reported):
            continue

        calculated = sum(components)

        difference = abs(
            calculated - reported
        )

        if difference > 1:

            add_failure(
                failures,
                "DQ-07",
                "WARNING",
                "cashflow",
                (
                    "Net cash mismatch: "
                    f"reported={reported}, "
                    f"calculated={calculated}, "
                    f"difference={difference}"
                ),
                row["company_id"],
                row["year"],
            )


# -------------------------------------------------------------------
# Validation Summary
# -------------------------------------------------------------------

def print_validation_summary(result):
    """
    Print a detailed validation summary.
    """

    print()
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    if result.empty:

        print()
        print(
            "All implemented DQ rules passed!"
        )

        return

    print()
    print("Failures by rule:")

    print(
        result["rule_id"]
        .value_counts()
        .sort_index()
    )

    print()
    print("Failures by severity:")

    print(
        result["severity"]
        .value_counts()
    )

    # ---------------------------------------------------------------
    # DQ-05 summary
    # ---------------------------------------------------------------

    dq05 = result[
        result["rule_id"] == "DQ-05"
    ]

    if not dq05.empty:

        print()
        print(
            "DQ-05 OPM classification:"
        )

        critical = (
            dq05["severity"]
            .eq("CRITICAL")
            .sum()
        )

        warning = (
            dq05["severity"]
            .eq("WARNING")
            .sum()
        )

        unusual = dq05[
            dq05["message"]
            .str.contains(
                "exceeds 100%",
                na=False,
            )
        ]

        print(
            f"  Critical OPM issues : "
            f"{critical}"
        )

        print(
            f"  Warning OPM issues  : "
            f"{warning}"
        )

        print(
            f"  Critical OPM >100%  : "
            f"{len(unusual)}"
        )

    # ---------------------------------------------------------------
    # DQ-06 summary
    # ---------------------------------------------------------------

    dq06 = result[
        result["rule_id"] == "DQ-06"
    ]

    if not dq06.empty:

        print()
        print(
            "DQ-06 Sales classification:"
        )

        print(
            f"  Sales issues        : "
            f"{len(dq06)}"
        )

    # ---------------------------------------------------------------
    # DQ-07 summary
    # ---------------------------------------------------------------

    dq07 = result[
        result["rule_id"] == "DQ-07"
    ]

    if not dq07.empty:

        print()
        print(
            "DQ-07 Cash-flow classification:"
        )

        print(
            f"  Cash-flow issues    : "
            f"{len(dq07)}"
        )


# -------------------------------------------------------------------
# Main Validator
# -------------------------------------------------------------------

def run_validation():

    print("=" * 70)
    print(
        "NIFTY 100 - DATA QUALITY VALIDATION"
    )
    print("=" * 70)

    datasets = load_all_sources()

    failures = []

    # ---------------------------------------------------------------
    # Run DQ rules
    # ---------------------------------------------------------------

    validate_pk_uniqueness(
        datasets,
        failures,
    )

    validate_company_year_uniqueness(
        datasets,
        failures,
    )

    validate_foreign_keys(
        datasets,
        failures,
    )

    validate_balance_sheet(
        datasets,
        failures,
    )

    validate_opm(
        datasets,
        failures,
    )

    validate_positive_sales(
        datasets,
        failures,
    )

    validate_net_cash(
        datasets,
        failures,
    )

    # ---------------------------------------------------------------
    # Create result dataframe
    # ---------------------------------------------------------------

    result = pd.DataFrame(
        failures
    )

    output_file = (
        OUTPUT_DIR
        / "validation_failures.csv"
    )

    result.to_csv(
        output_file,
        index=False,
    )

    print()
    print(
        f"Validation failures: "
        f"{len(result)}"
    )

    print(
        f"Report: {output_file}"
    )

    print_validation_summary(
        result
    )


if __name__ == "__main__":
    run_validation()