"""
SPRINT 6 - DAY 37
Cluster Profiling, Correlation Heatmap, Outlier Detection
and Portfolio Statistics.
"""

from pathlib import Path
import sqlite3
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "db" / "nifty100.sqlite3"
CLUSTER_PATH = ROOT / "output" / "cluster_labels.csv"
SECTOR_PATH = ROOT / "data" / "raw" / "sectors.xlsx"

OUTPUT_DIR = ROOT / "output"
REPORTS_DIR = ROOT / "reports"

OUTPUT_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

KPI_COLUMNS = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "cfo_pat_ratio",
]


# ---------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------

def load_ratios():

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        df = pd.read_sql_query(
            "SELECT * FROM financial_ratios",
            conn,
        )
    finally:
        conn.close()

    if df.empty:
        raise RuntimeError(
            "financial_ratios table is empty."
        )

    return df


def load_clusters():

    if not CLUSTER_PATH.exists():
        raise FileNotFoundError(
            f"Cluster labels not found: {CLUSTER_PATH}"
        )

    df = pd.read_csv(CLUSTER_PATH)

    required = {
        "company_id",
        "cluster_id",
        "cluster_name",
    }

    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            "cluster_labels.csv missing columns: "
            + ", ".join(sorted(missing))
        )

    return df


def load_sectors():

    if not SECTOR_PATH.exists():
        raise FileNotFoundError(
            f"Sector file not found: {SECTOR_PATH}"
        )

    df = pd.read_excel(
        SECTOR_PATH,
        header=0,
    )

    required = {
        "company_id",
        "broad_sector",
    }

    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            "sectors.xlsx missing columns: "
            + ", ".join(sorted(missing))
        )

    return (
        df[
            [
                "company_id",
                "broad_sector",
            ]
        ]
        .drop_duplicates(
            "company_id"
        )
    )


# ---------------------------------------------------------------------
# YEAR HANDLING
# ---------------------------------------------------------------------

def extract_year(value):

    if pd.isna(value):
        return np.nan

    match = re.search(
        r"(20\d{2})",
        str(value),
    )

    if match:
        return int(match.group(1))

    return np.nan


def select_latest_usable(ratios):

    df = ratios.copy()

    df["_year_num"] = (
        df["year"]
        .apply(extract_year)
    )

    df = df.dropna(
        subset=[
            "company_id",
            "_year_num",
        ]
    )

    for col in KPI_COLUMNS:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    # Prefer latest row with meaningful KPI data.
    usable = df[
        df[KPI_COLUMNS]
        .notna()
        .any(axis=1)
    ].copy()

    latest = (
        usable
        .sort_values(
            [
                "company_id",
                "_year_num",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .drop_duplicates(
            "company_id",
            keep="first",
        )
        .copy()
    )

    return latest


# ---------------------------------------------------------------------
# CLUSTER PROFILE
# ---------------------------------------------------------------------

def generate_cluster_profile(
    latest,
    clusters,
):

    df = latest.merge(
        clusters[
            [
                "company_id",
                "cluster_id",
                "cluster_name",
            ]
        ],
        on="company_id",
        how="inner",
    )

    profile_rows = []

    for (
        cluster_id,
        group,
    ) in df.groupby(
        [
            "cluster_id",
            "cluster_name",
        ]
    ):

        cluster_number, cluster_name = (
            cluster_id
        )

        row = {
            "cluster_id": cluster_number,
            "cluster_name": cluster_name,
            "company_count": len(group),
        }

        for metric in KPI_COLUMNS:

            values = pd.to_numeric(
                group[metric],
                errors="coerce",
            )

            row[
                f"{metric}_mean"
            ] = values.mean()

            row[
                f"{metric}_median"
            ] = values.median()

        profile_rows.append(row)

    profile = pd.DataFrame(
        profile_rows
    ).sort_values(
        "cluster_id"
    )

    path = (
        OUTPUT_DIR
        / "cluster_profile.csv"
    )

    profile.to_csv(
        path,
        index=False,
    )

    print(
        f"Cluster profile created: {path}"
    )

    return profile


# ---------------------------------------------------------------------
# CORRELATION HEATMAP
# ---------------------------------------------------------------------

def generate_correlation_heatmap(
    latest,
):

    available = [
        col
        for col in KPI_COLUMNS
        if col in latest.columns
    ]

    correlation = (
        latest[available]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .corr()
    )

    plt.figure(
        figsize=(12, 10)
    )

    plt.imshow(
        correlation,
        aspect="auto",
    )

    plt.colorbar(
        label="Correlation"
    )

    plt.xticks(
        range(len(available)),
        available,
        rotation=60,
        ha="right",
    )

    plt.yticks(
        range(len(available)),
        available,
    )

    plt.title(
        "NIFTY 100 Latest-Year KPI Correlation Heatmap"
    )

    plt.tight_layout()

    path = (
        REPORTS_DIR
        / "correlation_heatmap.png"
    )

    plt.savefig(
        path,
        dpi=180,
    )

    plt.close()

    print(
        f"Correlation heatmap created: {path}"
    )

    return correlation


# ---------------------------------------------------------------------
# SECTOR OUTLIERS
# ---------------------------------------------------------------------

def generate_outlier_report(
    latest,
    sectors,
):

    df = latest.merge(
        sectors,
        on="company_id",
        how="left",
    )

    outliers = []

    for sector, group in df.groupby(
        "broad_sector",
        dropna=False,
    ):

        for metric in KPI_COLUMNS:

            values = pd.to_numeric(
                group[metric],
                errors="coerce",
            )

            mean = values.mean()
            std = values.std(
                ddof=0
            )

            if pd.isna(std) or std == 0:
                continue

            z_scores = (
                values - mean
            ) / std

            for index, z in z_scores.items():

                if pd.isna(z):
                    continue

                if abs(z) > 3:

                    row = group.loc[index]

                    outliers.append(
                        {
                            "company_id": row[
                                "company_id"
                            ],
                            "broad_sector": sector,
                            "metric": metric,
                            "value": row[
                                metric
                            ],
                            "sector_mean": mean,
                            "sector_std": std,
                            "z_score": z,
                            "outlier_direction": (
                                "High"
                                if z > 0
                                else "Low"
                            ),
                        }
                    )

    report = pd.DataFrame(
        outliers
    )

    if report.empty:

        report = pd.DataFrame(
            columns=[
                "company_id",
                "broad_sector",
                "metric",
                "value",
                "sector_mean",
                "sector_std",
                "z_score",
                "outlier_direction",
            ]
        )

    else:

        report = report.sort_values(
            "z_score",
            key=lambda s: s.abs(),
            ascending=False,
        )

    path = (
        OUTPUT_DIR
        / "outlier_report.csv"
    )

    report.to_csv(
        path,
        index=False,
    )

    print(
        f"Outlier report created: {path}"
    )

    print(
        f"Outlier observations: {len(report)}"
    )

    return report


# ---------------------------------------------------------------------
# PORTFOLIO STATISTICS
# ---------------------------------------------------------------------

def generate_portfolio_stats(
    latest,
):

    rows = []

    for metric in KPI_COLUMNS:

        values = pd.to_numeric(
            latest[metric],
            errors="coerce",
        ).dropna()

        if values.empty:
            continue

        rows.append(
            {
                "metric": metric,
                "P10": values.quantile(0.10),
                "P25": values.quantile(0.25),
                "P50": values.quantile(0.50),
                "P75": values.quantile(0.75),
                "P90": values.quantile(0.90),
                "Mean": values.mean(),
                "Std": values.std(
                    ddof=1
                ),
                "Count": len(values),
            }
        )

    stats = pd.DataFrame(
        rows
    )

    path = (
        OUTPUT_DIR
        / "portfolio_stats.csv"
    )

    stats.to_csv(
        path,
        index=False,
    )

    print(
        f"Portfolio statistics created: {path}"
    )

    return stats


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    print("=" * 70)
    print(
        "SPRINT 6 - DAY 37"
    )
    print(
        "CLUSTER PROFILING + KPI ANALYSIS"
    )
    print("=" * 70)

    # 1. Load.
    print(
        "\n[1/5] Loading data..."
    )

    ratios = load_ratios()
    clusters = load_clusters()
    sectors = load_sectors()

    print(
        f"Financial ratio rows: {len(ratios)}"
    )

    print(
        f"Cluster rows: {len(clusters)}"
    )

    print(
        f"Sector rows: {len(sectors)}"
    )

    # 2. Latest dataset.
    print(
        "\n[2/5] Selecting latest usable annual data..."
    )

    latest = select_latest_usable(
        ratios
    )

    print(
        f"Latest company rows: {len(latest)}"
    )

    if len(latest) != 92:
        raise RuntimeError(
            f"Expected 92 latest company rows, "
            f"got {len(latest)}"
        )

    # 3. Cluster profile.
    print(
        "\n[3/5] Generating cluster profile..."
    )

    profile = generate_cluster_profile(
        latest,
        clusters,
    )

    # 4. Correlation.
    print(
        "\n[4/5] Generating correlation heatmap..."
    )

    correlation = (
        generate_correlation_heatmap(
            latest
        )
    )

    # 5. Outliers + portfolio stats.
    print(
        "\n[5/5] Generating outliers and portfolio statistics..."
    )

    outliers = generate_outlier_report(
        latest,
        sectors,
    )

    stats = generate_portfolio_stats(
        latest
    )

    # ---------------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------------

    print("\n")
    print("=" * 70)
    print(
        "DAY 37 VALIDATION"
    )
    print("=" * 70)

    print(
        f"Latest company rows : {len(latest)}"
    )

    print(
        f"Cluster profile rows: {len(profile)}"
    )

    print(
        f"Clusters represented: "
        f"{profile['cluster_id'].nunique()}"
    )

    print(
        f"Correlation KPIs    : "
        f"{len(correlation)}"
    )

    print(
        f"Outlier observations: "
        f"{len(outliers)}"
    )

    print(
        f"Portfolio KPI stats : "
        f"{len(stats)}"
    )

    print(
        "\nCluster sizes:"
    )

    print(
        clusters
        .groupby(
            [
                "cluster_id",
                "cluster_name",
            ]
        )
        .size()
        .to_string()
    )

    print(
        "\nPortfolio statistics:"
    )

    print(
        stats.round(2).to_string(
            index=False
        )
    )

    # Hard gates.
    assert len(latest) == 92

    assert (
        clusters["company_id"]
        .nunique()
        == 92
    )

    assert (
        clusters["cluster_id"]
        .nunique()
        == 5
    )

    assert (
        profile["cluster_id"]
        .nunique()
        == 5
    )

    assert len(stats) == 10

    assert correlation.shape == (
        10,
        10,
    )

    assert (
        Path(
            OUTPUT_DIR
            / "cluster_profile.csv"
        ).exists()
    )

    assert (
        Path(
            OUTPUT_DIR
            / "outlier_report.csv"
        ).exists()
    )

    assert (
        Path(
            OUTPUT_DIR
            / "portfolio_stats.csv"
        ).exists()
    )

    assert (
        Path(
            REPORTS_DIR
            / "correlation_heatmap.png"
        ).exists()
    )

    print("\n")
    print("=" * 70)
    print(
        "DAY 37 COMPLETE - PASS"
    )
    print("=" * 70)

    print(
        "\nCreated:"
    )

    print(
        "  output/cluster_profile.csv"
    )

    print(
        "  output/outlier_report.csv"
    )

    print(
        "  output/portfolio_stats.csv"
    )

    print(
        "  reports/correlation_heatmap.png"
    )


if __name__ == "__main__":
    main()