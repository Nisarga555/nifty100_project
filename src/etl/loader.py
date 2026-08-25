from pathlib import Path

import pandas as pd

from src.etl.normaliser import normalize_dataframe


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(exist_ok=True)


SOURCE_FILES = {
    "companies": "companies.xlsx",
    "profitandloss": "profitandloss.xlsx",
    "balancesheet": "balancesheet.xlsx",
    "cashflow": "cashflow.xlsx",
    "analysis": "analysis.xlsx",
    "documents": "documents.xlsx",
    "prosandcons": "prosandcons.xlsx",
    "sectors": "sectors.xlsx",
    "stock_prices": "stock_prices.xlsx",
    "financial_ratios": "financial_ratios.xlsx",
    "peer_groups": "peer_groups.xlsx",
    "market_cap": "market_cap.xlsx",
}


# Tables where company_id + year must be unique
PERIOD_UNIQUE_TABLES = {
    "profitandloss",
    "balancesheet",
    "cashflow",
    "documents",
    "financial_ratios",
    "market_cap",
}


def read_excel_file(file_path):
    """Read a source Excel file."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Source file not found: {file_path}"
        )

    return pd.read_excel(file_path)


def load_source(source_name):
    """
    Load and normalize one source dataset.
    """

    if source_name not in SOURCE_FILES:
        raise ValueError(
            f"Unknown source: {source_name}"
        )

    file_path = RAW_DIR / SOURCE_FILES[source_name]

    df = read_excel_file(file_path)

    df = normalize_dataframe(df)

    return df


def normalize_company_id_set(companies_df):
    """
    Create the authoritative set of valid company IDs
    from the companies master table.
    """

    return set(
        companies_df["id"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
    )


def reject_orphan_rows(
    table_name,
    df,
    valid_company_ids,
    rejected_rows,
):
    """
    Reject rows whose company_id does not exist
    in companies.id.

    Rejected rows are logged but the original
    Excel source file is never modified.
    """

    if "company_id" not in df.columns:
        return df

    company_ids = (
        df["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    invalid_mask = (
        df["company_id"].notna()
        & ~company_ids.isin(valid_company_ids)
    )

    invalid_rows = df[invalid_mask].copy()

    if invalid_rows.empty:
        return df

    for _, row in invalid_rows.iterrows():

        rejected_rows.append(
            {
                "table_name": table_name,
                "company_id": row["company_id"],
                "year": row.get("year"),
                "reason": (
                    "Unknown company_id - "
                    "not present in companies.id"
                ),
            }
        )

    valid_df = df[~invalid_mask].copy()

    return valid_df.reset_index(drop=True)


def deduplicate_period_rows(
    table_name,
    df,
    deduplicated_rows,
):
    """
    Deduplicate company_id + year combinations.

    The project DQ rule requires duplicate period
    records to be resolved by keeping the last
    occurrence.

    The original source data is never modified.
    """

    if table_name not in PERIOD_UNIQUE_TABLES:
        return df

    required_columns = {
        "company_id",
        "year",
    }

    if not required_columns.issubset(df.columns):
        return df

    duplicate_mask = df.duplicated(
        subset=["company_id", "year"],
        keep=False,
    )

    duplicate_rows = df[duplicate_mask].copy()

    if duplicate_rows.empty:
        return df

    # Log every duplicate row that will be removed.
    # The final occurrence is retained.
    rows_to_remove = df.duplicated(
        subset=["company_id", "year"],
        keep="last",
    )

    removed_rows = df[rows_to_remove].copy()

    for _, row in removed_rows.iterrows():

        deduplicated_rows.append(
            {
                "table_name": table_name,
                "company_id": row["company_id"],
                "year": row["year"],
                "id": row.get("id"),
                "reason": (
                    "Duplicate company_id + year - "
                    "kept last occurrence"
                ),
            }
        )

    cleaned_df = df[~rows_to_remove].copy()

    return cleaned_df.reset_index(drop=True)


def load_all_sources():
    """
    Load all 12 source datasets.

    ETL pipeline:

        Raw Excel
            ↓
        Normalization
            ↓
        Company FK validation
            ↓
        Reject orphan rows
            ↓
        Deduplicate company_id + year
            ↓
        Clean datasets
            ↓
        Audit reports
    """

    datasets = {}

    rejected_rows = []
    deduplicated_rows = []
    audit_rows = []

    print("=" * 70)
    print("NIFTY 100 - SOURCE DATA LOADER")
    print("=" * 70)

    # ---------------------------------------------------------------
    # STEP 1
    # Load companies master first
    # ---------------------------------------------------------------

    companies = load_source("companies")

    datasets["companies"] = companies

    valid_company_ids = normalize_company_id_set(
        companies
    )

    audit_rows.append(
        {
            "table_name": "companies",
            "source_rows": len(companies),
            "orphan_rows_rejected": 0,
            "duplicate_rows_removed": 0,
            "loaded_rows": len(companies),
            "status": "OK",
        }
    )

    print(
        f"[OK] {'companies':<20} "
        f"rows={len(companies):<6} "
        f"columns={len(companies.columns)}"
    )

    # ---------------------------------------------------------------
    # STEP 2
    # Load remaining datasets
    # ---------------------------------------------------------------

    for source_name in SOURCE_FILES:

        if source_name == "companies":
            continue

        try:

            df = load_source(source_name)

            source_rows = len(df)

            # -------------------------------------------------------
            # Reject orphan company IDs
            # -------------------------------------------------------

            before_orphan_rejection = len(df)

            df = reject_orphan_rows(
                source_name,
                df,
                valid_company_ids,
                rejected_rows,
            )

            orphan_count = (
                before_orphan_rejection - len(df)
            )

            # -------------------------------------------------------
            # Deduplicate company_id + year
            # -------------------------------------------------------

            before_deduplication = len(df)

            df = deduplicate_period_rows(
                source_name,
                df,
                deduplicated_rows,
            )

            duplicate_count = (
                before_deduplication - len(df)
            )

            # -------------------------------------------------------
            # Store cleaned dataset
            # -------------------------------------------------------

            datasets[source_name] = df

            audit_rows.append(
                {
                    "table_name": source_name,
                    "source_rows": source_rows,
                    "orphan_rows_rejected": orphan_count,
                    "duplicate_rows_removed": duplicate_count,
                    "loaded_rows": len(df),
                    "status": (
                        "OK"
                        if orphan_count == 0
                        and duplicate_count == 0
                        else "CLEANED"
                    ),
                }
            )

            print(
                f"[OK] {source_name:<20} "
                f"rows={len(df):<6} "
                f"columns={len(df.columns)}"
            )

            if orphan_count > 0:

                print(
                    f"     [REJECTED] "
                    f"{orphan_count} orphan rows"
                )

            if duplicate_count > 0:

                print(
                    f"     [DEDUPLICATED] "
                    f"{duplicate_count} duplicate rows"
                )

        except Exception as error:

            print(
                f"[ERROR] {source_name}: {error}"
            )

            audit_rows.append(
                {
                    "table_name": source_name,
                    "source_rows": 0,
                    "orphan_rows_rejected": 0,
                    "duplicate_rows_removed": 0,
                    "loaded_rows": 0,
                    "status": f"ERROR: {error}",
                }
            )

    # ---------------------------------------------------------------
    # STEP 3
    # Save orphan rejection report
    # ---------------------------------------------------------------

    rejection_file = (
        OUTPUT_DIR / "rejected_orphans.csv"
    )

    if rejected_rows:

        rejected_df = pd.DataFrame(
            rejected_rows
        )

        rejected_df.to_csv(
            rejection_file,
            index=False,
        )

    else:

        pd.DataFrame(
            columns=[
                "table_name",
                "company_id",
                "year",
                "reason",
            ]
        ).to_csv(
            rejection_file,
            index=False,
        )

    # ---------------------------------------------------------------
    # STEP 4
    # Save duplicate/deduplication report
    # ---------------------------------------------------------------

    duplicate_file = (
        OUTPUT_DIR / "deduplicated_rows.csv"
    )

    if deduplicated_rows:

        duplicate_df = pd.DataFrame(
            deduplicated_rows
        )

        duplicate_df.to_csv(
            duplicate_file,
            index=False,
        )

    else:

        pd.DataFrame(
            columns=[
                "table_name",
                "company_id",
                "year",
                "id",
                "reason",
            ]
        ).to_csv(
            duplicate_file,
            index=False,
        )

    # ---------------------------------------------------------------
    # STEP 5
    # Save ETL load audit
    # ---------------------------------------------------------------

    audit_file = (
        OUTPUT_DIR / "load_audit.csv"
    )

    audit_df = pd.DataFrame(
        audit_rows
    )

    audit_df.to_csv(
        audit_file,
        index=False,
    )

    # ---------------------------------------------------------------
    # STEP 6
    # Print audit summary
    # ---------------------------------------------------------------

    print()
    print("=" * 70)
    print("ETL AUDIT")
    print("=" * 70)

    print(
        f"Valid companies: "
        f"{len(valid_company_ids)}"
    )

    print(
        f"Rejected orphan rows: "
        f"{len(rejected_rows)}"
    )

    print(
        f"Duplicate rows removed: "
        f"{len(deduplicated_rows)}"
    )

    print(
        f"Audit report: "
        f"{audit_file}"
    )

    print(
        f"Orphan report: "
        f"{rejection_file}"
    )

    print(
        f"Deduplication report: "
        f"{duplicate_file}"
    )

    return datasets


def show_columns(datasets):
    """Display normalized columns for every dataset."""

    print("\n" + "=" * 70)
    print("NORMALIZED COLUMN SUMMARY")
    print("=" * 70)

    for name, df in datasets.items():

        print(f"\n{name}")
        print("-" * 50)

        for column in df.columns:
            print(f"  {column}")


def main():

    datasets = load_all_sources()

    print(
        "\nSuccessfully loaded:",
        len(datasets),
        "/",
        len(SOURCE_FILES),
    )

    show_columns(datasets)


if __name__ == "__main__":
    main()