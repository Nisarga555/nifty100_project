import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ================================================================
# PROJECT ROOT
# ================================================================

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ================================================================
# PATHS
# ================================================================

DB_PATH = ROOT / "db" / "nifty100.sqlite3"

PEER_GROUPS_PATH = ROOT / "data" / "raw" / "peer_groups.xlsx"


# ================================================================
# REQUIRED PEER METRICS
# ================================================================

PEER_METRICS = {
    "roe": "return_on_equity_pct",
    "roce": "return_on_capital_employed_pct",
    "npm": "net_profit_margin_pct",
    "de": "debt_to_equity",
    "fcf": "free_cash_flow_cr",
    "pat_cagr_5yr": "pat_cagr_5yr",
    "revenue_cagr_5yr": "revenue_cagr_5yr",
    "eps_cagr_5yr": "eps_cagr_5yr",
    "icr": "interest_coverage",
    "asset_turnover": "asset_turnover",
}


# ================================================================
# LOAD PEER GROUPS
# ================================================================


def load_peer_groups(path=PEER_GROUPS_PATH):

    if not path.exists():
        raise FileNotFoundError(f"Peer groups file not found: {path}")

    dataframe = pd.read_excel(path)

    dataframe.columns = [str(column).strip() for column in dataframe.columns]

    required_columns = {
        "peer_group_name",
        "company_id",
    }

    missing = required_columns - set(dataframe.columns)

    if missing:
        raise ValueError(
            "peer_groups.xlsx is missing columns: " + ", ".join(sorted(missing))
        )

    dataframe["company_id"] = (
        dataframe["company_id"].astype(str).str.strip().str.upper()
    )

    dataframe["peer_group_name"] = dataframe["peer_group_name"].astype(str).str.strip()

    dataframe = dataframe[
        dataframe["company_id"].ne("") & dataframe["peer_group_name"].ne("")
    ].copy()

    dataframe = dataframe.drop_duplicates(
        subset=[
            "peer_group_name",
            "company_id",
        ]
    )

    return dataframe.reset_index(drop=True)


# ================================================================
# YEAR PARSER
# ================================================================


def parse_year(value):

    if pd.isna(value):
        return np.nan

    match = re.search(
        r"(19|20)\d{2}",
        str(value),
    )

    if not match:
        return np.nan

    return int(match.group(0))


# ================================================================
# LOAD FINANCIAL RATIOS
# ================================================================


def load_financial_ratios():

    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)

    try:

        dataframe = pd.read_sql_query(
            "SELECT * FROM financial_ratios",
            connection,
        )

    finally:

        connection.close()

    if dataframe.empty:
        raise ValueError("financial_ratios table is empty.")

    dataframe["company_id"] = (
        dataframe["company_id"].astype(str).str.strip().str.upper()
    )

    dataframe["_parsed_year"] = dataframe["year"].apply(parse_year)

    dataframe = dataframe[dataframe["_parsed_year"].notna()].copy()

    dataframe["_parsed_year"] = dataframe["_parsed_year"].astype(int)

    return dataframe


# ================================================================
# LATEST AVAILABLE NON-NULL METRIC
# ================================================================


def select_latest_metric_values(ratios):
    """
    For every company and every required metric, select the
    latest available non-null value.

    This is intentionally metric-by-metric.

    Example:
        ROE may be available in 2024
        FCF may only be available in 2023

    We use 2024 ROE and 2023 FCF rather than losing FCF
    simply because it is missing from the latest row.

    No values are fabricated.
    """

    records = []

    dataframe = ratios.copy()

    dataframe = dataframe.sort_values(
        [
            "company_id",
            "_parsed_year",
        ],
        ascending=[
            True,
            False,
        ],
    )

    for company_id, company_rows in dataframe.groupby(
        "company_id",
        sort=False,
    ):

        for metric_name, column_name in PEER_METRICS.items():

            if column_name not in company_rows.columns:
                continue

            values = pd.to_numeric(
                company_rows[column_name],
                errors="coerce",
            )

            valid_mask = values.notna()

            if not valid_mask.any():
                continue

            first_valid_index = values[valid_mask].index[0]

            selected_value = values.loc[first_valid_index]

            selected_year = company_rows.loc[
                first_valid_index,
                "year",
            ]

            parsed_year = company_rows.loc[
                first_valid_index,
                "_parsed_year",
            ]

            records.append(
                {
                    "company_id": company_id,
                    "metric": metric_name,
                    "value": float(selected_value),
                    "year": selected_year,
                    "_parsed_year": parsed_year,
                }
            )

    result = pd.DataFrame(records)

    if result.empty:
        return pd.DataFrame(
            columns=[
                "company_id",
                "metric",
                "value",
                "year",
                "_parsed_year",
            ]
        )

    return result


# ================================================================
# BUILD PEER DATASET
# ================================================================


def build_peer_dataset(
    ratios,
    peer_groups,
):

    latest_metrics = select_latest_metric_values(ratios)

    merged = peer_groups.merge(
        latest_metrics,
        on="company_id",
        how="left",
    )

    return merged


# ================================================================
# PERCENT RANK
# ================================================================


def calculate_percent_rank(series):

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    valid = numeric.dropna()

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float,
    )

    count = len(valid)

    if count == 0:
        return result

    if count == 1:

        result.loc[valid.index] = 100.0

        return result

    ranks = valid.rank(
        method="average",
        ascending=True,
    )

    result.loc[valid.index] = (ranks - 1) / (count - 1) * 100

    return result


# ================================================================
# D/E INVERSE PERCENTILE
# ================================================================


def calculate_de_percent_rank(series):

    normal_rank = calculate_percent_rank(series)

    result = 100.0 - normal_rank

    return result


# ================================================================
# CALCULATE ALL PEER PERCENTILES
# ================================================================


def calculate_peer_percentiles(
    peer_dataset,
):

    records = []

    grouped = peer_dataset.groupby(
        "peer_group_name",
        dropna=False,
    )

    for (
        peer_group_name,
        group,
    ) in grouped:

        for metric_name in PEER_METRICS:

            metric_rows = group[group["metric"] == metric_name].copy()

            if metric_rows.empty:
                continue

            values = pd.to_numeric(
                metric_rows["value"],
                errors="coerce",
            )

            valid_mask = values.notna()

            if not valid_mask.any():
                continue

            if metric_name == "de":

                percentiles = calculate_de_percent_rank(values)

            else:

                percentiles = calculate_percent_rank(values)

            for index in metric_rows.index:

                value = values.loc[index]

                percentile = percentiles.loc[index]

                if pd.isna(value):
                    continue

                records.append(
                    {
                        "company_id": metric_rows.loc[
                            index,
                            "company_id",
                        ],
                        "peer_group_name": peer_group_name,
                        "metric": metric_name,
                        "value": float(value),
                        "percentile_rank": float(percentile),
                        "year": metric_rows.loc[
                            index,
                            "year",
                        ],
                    }
                )

    return pd.DataFrame(
        records,
        columns=[
            "company_id",
            "peer_group_name",
            "metric",
            "value",
            "percentile_rank",
            "year",
        ],
    )


# ================================================================
# CREATE SQLITE TABLE
# ================================================================


def create_peer_percentiles_table(
    connection,
):

    connection.execute("""
        CREATE TABLE IF NOT EXISTS peer_percentiles (
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year TEXT
        )
        """)

    connection.commit()


# ================================================================
# SAVE PEER RESULTS
# ================================================================


def save_peer_percentiles(
    dataframe,
):

    connection = sqlite3.connect(DB_PATH)

    try:

        create_peer_percentiles_table(connection)

        connection.execute("DELETE FROM peer_percentiles")

        dataframe.to_sql(
            "peer_percentiles",
            connection,
            if_exists="append",
            index=False,
        )

        connection.commit()

    finally:

        connection.close()


# ================================================================
# VALIDATE RESULTS
# ================================================================


def validate_peer_results(
    peer_groups,
    percentiles,
):

    print("\n[VALIDATION] Peer groups:")

    group_count = peer_groups["peer_group_name"].nunique()

    print(f"[CHECK] Unique peer groups: " f"{group_count}")

    print(f"[CHECK] Assignments: " f"{len(peer_groups)}")

    print(f"[CHECK] Percentile rows: " f"{len(percentiles)}")

    # ------------------------------------------------------------
    # Peer group count
    # ------------------------------------------------------------

    if group_count != 11:

        raise RuntimeError(f"Expected 11 peer groups, " f"found {group_count}.")

    # ------------------------------------------------------------
    # Percentile range
    # ------------------------------------------------------------

    if not percentiles.empty:

        minimum = percentiles["percentile_rank"].min()

        maximum = percentiles["percentile_rank"].max()

        print(f"[CHECK] Percentile range: " f"{minimum:.2f} - {maximum:.2f}")

        if minimum < 0 or maximum > 100:

            raise RuntimeError("Percentile rank outside 0-100.")

        print("[OK] Percentile ranks within 0-100")

    # ------------------------------------------------------------
    # Metric count
    # ------------------------------------------------------------

    metric_names = set(percentiles["metric"].unique())

    expected_metrics = set(PEER_METRICS.keys())

    print(f"[CHECK] Metrics represented: " f"{len(metric_names)}")

    missing_metrics = expected_metrics - metric_names

    if missing_metrics:

        raise RuntimeError(
            "Missing peer metrics: " + ", ".join(sorted(missing_metrics))
        )

    print("[OK] All 10 peer metrics represented")

    # ------------------------------------------------------------
    # Metric coverage PER PEER GROUP
    # ------------------------------------------------------------

    print("\n[CHECK] Metric coverage per peer group:")

    expected_metric_count = len(PEER_METRICS)

    coverage = (
        percentiles.groupby("peer_group_name")["metric"]
        .nunique()
        .sort_values(ascending=False)
    )

    incomplete_groups = []

    for (
        group_name,
        metric_count,
    ) in coverage.items():

        print(
            f"        {group_name:<30} "
            f"{metric_count:>2}/"
            f"{expected_metric_count} metrics"
        )

        if metric_count != expected_metric_count:
            incomplete_groups.append(group_name)

    if incomplete_groups:

        raise RuntimeError(
            "Incomplete metric coverage for: " + ", ".join(incomplete_groups)
        )

    print("[OK] Every peer group has all 10 metrics")

    # ------------------------------------------------------------
    # D/E inverse ranking
    # ------------------------------------------------------------

    if "de" in metric_names:

        de_rows = percentiles[percentiles["metric"] == "de"]

        print(f"\n[CHECK] D/E percentile rows: " f"{len(de_rows)}")

        print("[OK] D/E inverse percentile " "calculation applied")

    # ------------------------------------------------------------
    # Company coverage
    # ------------------------------------------------------------

    assigned_companies = peer_groups["company_id"].nunique()

    percentile_companies = percentiles["company_id"].nunique()

    print(f"\n[CHECK] Peer-assigned companies: " f"{assigned_companies}")

    print(f"[CHECK] Companies represented in " f"percentiles: {percentile_companies}")

    if percentile_companies != assigned_companies:

        missing_companies = sorted(
            set(peer_groups["company_id"]) - set(percentiles["company_id"])
        )

        raise RuntimeError(
            "Some peer-assigned companies have "
            "no percentile records: " + ", ".join(missing_companies)
        )

    print("[OK] All peer-assigned companies represented")

    # ------------------------------------------------------------
    # Peer group coverage
    # ------------------------------------------------------------

    print("\n[CHECK] Peer group company coverage:")

    coverage_companies = (
        percentiles.groupby("peer_group_name")["company_id"]
        .nunique()
        .sort_values(ascending=False)
    )

    for (
        group_name,
        count,
    ) in coverage_companies.items():

        print(f"        {group_name:<30} " f"{count:>3} companies")


# ================================================================
# MAIN
# ================================================================


def main():

    print("=" * 70)

    print("NIFTY 100 - SPRINT 3 DAY 18")

    print("PEER PERCENTILE ENGINE")

    print("=" * 70)

    # ------------------------------------------------------------
    # STEP 1
    # ------------------------------------------------------------

    print("\n[1] Loading peer groups...")

    peer_groups = load_peer_groups()

    print(f"[OK] Peer group rows: " f"{len(peer_groups)}")

    print(f"[OK] Peer groups: " f"{peer_groups['peer_group_name'].nunique()}")

    print(f"[OK] Companies assigned: " f"{peer_groups['company_id'].nunique()}")

    # ------------------------------------------------------------
    # STEP 2
    # ------------------------------------------------------------

    print("\n[2] Loading financial ratios...")

    ratios = load_financial_ratios()

    print(f"[OK] financial_ratios rows: " f"{len(ratios):,}")

    # ------------------------------------------------------------
    # STEP 3
    # ------------------------------------------------------------

    print("\n[3] Building peer dataset...")

    peer_dataset = build_peer_dataset(
        ratios,
        peer_groups,
    )

    print(f"[OK] Peer dataset rows: " f"{len(peer_dataset)}")

    print(f"[OK] Metric rows: " f"{len(peer_dataset):,}")

    # ------------------------------------------------------------
    # STEP 4
    # ------------------------------------------------------------

    print("\n[4] Calculating percentile rankings...")

    percentiles = calculate_peer_percentiles(peer_dataset)

    print(f"[OK] Percentile rows generated: " f"{len(percentiles)}")

    # ------------------------------------------------------------
    # STEP 5
    # ------------------------------------------------------------

    print("\n[5] Validating results...")

    validate_peer_results(
        peer_groups,
        percentiles,
    )

    # ------------------------------------------------------------
    # STEP 6
    # ------------------------------------------------------------

    print("\n[6] Saving peer_percentiles " "to SQLite...")

    save_peer_percentiles(percentiles)

    print("[OK] peer_percentiles table updated")

    # ------------------------------------------------------------
    # FINAL
    # ------------------------------------------------------------

    print("\n" + "=" * 70)

    print("DAY 18 PEER ENGINE COMPLETE")

    print("=" * 70)


if __name__ == "__main__":
    main()
