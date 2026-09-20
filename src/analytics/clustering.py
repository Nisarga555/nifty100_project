"""
SPRINT 6 - DAY 36
K-MEANS CLUSTERING

Clusters all 92 NIFTY 100 companies into 5 labelled archetypes.

Required clustering features:
1. return_on_equity_pct
2. debt_to_equity
3. revenue_cagr_5yr
4. fcf_cagr_5yr
5. operating_profit_margin_pct

Source:
    db/nifty100.sqlite3 -> financial_ratios
    data/raw/companies.xlsx -> company names
    data/raw/sectors.xlsx -> sector mapping

Outputs:
    output/cluster_labels.csv
    reports/elbow_plot.png
"""

import re
import sqlite3
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

DB_PATH = ROOT / "db" / "nifty100.sqlite3"
RAW_DIR = ROOT / "data" / "raw"

OUTPUT_DIR = ROOT / "output"
REPORTS_DIR = ROOT / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# REQUIRED FEATURES
# ---------------------------------------------------------------------

FEATURES = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


def extract_year(value):
    """Extract a four-digit year from labels such as Mar 2024 or Sep 2024."""

    if pd.isna(value):
        return np.nan

    match = re.search(r"(20\d{2})", str(value))

    if match:
        return int(match.group(1))

    return np.nan


def find_excel_file(keyword):
    """Find an Excel source file by keyword."""

    candidates = sorted(
        [p for p in RAW_DIR.glob("*.xlsx") if keyword.lower() in p.stem.lower()]
    )

    if not candidates:
        raise FileNotFoundError(
            f"Could not find an Excel file containing '{keyword}' " f"inside {RAW_DIR}"
        )

    return candidates[0]


# ---------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------


def load_ratios():
    """Load the existing Sprint 2 financial ratios table."""

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    try:
        ratios = pd.read_sql_query(
            "SELECT * FROM financial_ratios",
            conn,
        )
    finally:
        conn.close()

    if ratios.empty:
        raise RuntimeError("financial_ratios table is empty.")

    print(f"Financial ratio rows loaded: {len(ratios)}")

    return ratios


# ---------------------------------------------------------------------
# COMPANY MASTER
# ---------------------------------------------------------------------


def load_companies():
    """Load the company master Excel file."""

    path = find_excel_file("companies")

    print(f"Company source: {path.name}")

    # Sprint 1 companies source uses header row 1.
    companies = pd.read_excel(
        path,
        header=1,
    )

    required = {
        "id",
        "company_name",
    }

    missing = required - set(companies.columns)

    if missing:
        raise RuntimeError(
            "Companies file is missing columns: " + ", ".join(sorted(missing))
        )

    companies = companies[["id", "company_name"]].copy()

    companies["id"] = companies["id"].astype(str).str.strip()

    companies["company_name"] = companies["company_name"].astype(str).str.strip()

    companies = companies.drop_duplicates(
        subset=["id"],
        keep="first",
    )

    return companies


# ---------------------------------------------------------------------
# SECTORS
# ---------------------------------------------------------------------


def load_sectors():
    """Load the Sprint 1 sector mapping."""

    path = find_excel_file("sectors")

    print(f"Sector source: {path.name}")

    sectors = pd.read_excel(
        path,
        header=0,
    )

    required = {
        "company_id",
        "broad_sector",
    }

    missing = required - set(sectors.columns)

    if missing:
        raise RuntimeError(
            "Sectors file is missing columns: " + ", ".join(sorted(missing))
        )

    sectors = sectors[["company_id", "broad_sector"]].copy()

    sectors["company_id"] = sectors["company_id"].astype(str).str.strip()

    sectors["broad_sector"] = sectors["broad_sector"].astype(str).str.strip()

    sectors = sectors.drop_duplicates(
        subset=["company_id"],
        keep="first",
    )

    return sectors


# ---------------------------------------------------------------------
# FCF CAGR
# ---------------------------------------------------------------------


def calculate_fcf_cagr_5yr(ratios):
    """
    Calculate five-year FCF CAGR.

    Uses the existing free_cash_flow_cr field from financial_ratios.

    CAGR is calculated only when:
        - exact five-year historical endpoint exists
        - starting FCF > 0
        - ending FCF > 0
    """

    df = ratios[
        [
            "company_id",
            "year",
            "free_cash_flow_cr",
        ]
    ].copy()

    df["_year_num"] = df["year"].apply(extract_year)

    df["free_cash_flow_cr"] = pd.to_numeric(
        df["free_cash_flow_cr"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "company_id",
            "_year_num",
            "free_cash_flow_cr",
        ]
    )

    results = []

    for company_id, group in df.groupby("company_id"):

        values = {}

        for _, row in group.iterrows():

            year = int(row["_year_num"])
            value = float(row["free_cash_flow_cr"])

            values[year] = value

        if not values:
            continue

        end_year = max(values)

        start_year = end_year - 5

        if start_year not in values:
            continue

        start_value = values[start_year]
        end_value = values[end_year]

        if start_value > 0 and end_value > 0:

            cagr = ((end_value / start_value) ** (1 / 5) - 1) * 100

            results.append(
                {
                    "company_id": company_id,
                    "fcf_cagr_5yr": cagr,
                }
            )

    result = pd.DataFrame(results)

    if result.empty:
        return pd.DataFrame(
            columns=[
                "company_id",
                "fcf_cagr_5yr",
            ]
        )

    return result


# ---------------------------------------------------------------------
# LATEST ANNUAL DATA
# ---------------------------------------------------------------------


def select_latest_rows(ratios):
    """
    Select the latest usable annual financial-ratio row
    for each company.
    """

    df = ratios.copy()

    df["_year_num"] = df["year"].apply(extract_year)

    df = df.dropna(
        subset=[
            "company_id",
            "_year_num",
        ]
    )

    # Numeric conversion.
    for column in [
        "return_on_equity_pct",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "operating_profit_margin_pct",
        "free_cash_flow_cr",
    ]:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    # Require at least one of the primary
    # clustering metrics to be present.
    primary_metrics = [
        "return_on_equity_pct",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "operating_profit_margin_pct",
    ]

    available_metrics = [c for c in primary_metrics if c in df.columns]

    usable = df[df[available_metrics].notna().any(axis=1)].copy()

    # Latest usable year per company.
    latest = usable.sort_values(
        [
            "company_id",
            "_year_num",
        ],
        ascending=[
            True,
            False,
        ],
    ).drop_duplicates(
        subset=["company_id"],
        keep="first",
    )

    return latest


# ---------------------------------------------------------------------
# FEATURE MATRIX
# ---------------------------------------------------------------------


def build_feature_matrix(
    companies,
    sectors,
    ratios,
):

    latest = select_latest_rows(ratios)

    print(f"Latest usable company rows: " f"{len(latest)}")

    # Calculate FCF CAGR separately.
    fcf_cagr = calculate_fcf_cagr_5yr(ratios)

    # Required existing features.
    feature_df = latest[
        [
            "company_id",
            "return_on_equity_pct",
            "debt_to_equity",
            "revenue_cagr_5yr",
            "operating_profit_margin_pct",
        ]
    ].copy()

    # Attach FCF CAGR.
    feature_df = feature_df.merge(
        fcf_cagr,
        on="company_id",
        how="left",
    )

    # Company names.
    feature_df = feature_df.merge(
        companies,
        left_on="company_id",
        right_on="id",
        how="left",
    )

    feature_df = feature_df.drop(columns=["id"])

    # Sector.
    feature_df = feature_df.merge(
        sectors,
        on="company_id",
        how="left",
    )

    return feature_df


# ---------------------------------------------------------------------
# SECTOR MEDIAN IMPUTATION
# ---------------------------------------------------------------------


def impute_sector_medians(df):

    result = df.copy()

    print("\nMissing values before imputation:")

    print(result[FEATURES].isna().sum().to_string())

    for feature in FEATURES:

        result[feature] = pd.to_numeric(
            result[feature],
            errors="coerce",
        )

    # Sector median first.
    for feature in FEATURES:

        result[feature] = result.groupby("broad_sector")[feature].transform(
            lambda s: s.fillna(s.median())
        )

    # Overall median fallback.
    for feature in FEATURES:

        median = result[feature].median()

        result[feature] = result[feature].fillna(median)

    # Final zero fallback only if absolutely necessary.
    for feature in FEATURES:

        result[feature] = result[feature].fillna(0)

    print("\nMissing values after imputation:")

    print(result[FEATURES].isna().sum().to_string())

    return result


# ---------------------------------------------------------------------
# ELBOW PLOT
# ---------------------------------------------------------------------


def create_elbow_plot(X_scaled):

    k_values = range(2, 9)

    inertias = []

    for k in k_values:

        model = KMeans(
            n_clusters=k,
            random_state=42,
            n_init=20,
        )

        model.fit(X_scaled)

        inertias.append(model.inertia_)

    plt.figure(figsize=(9, 6))

    plt.plot(
        list(k_values),
        inertias,
        marker="o",
    )

    plt.xlabel("Number of Clusters (K)")

    plt.ylabel("Inertia")

    plt.title("K-Means Elbow Plot - NIFTY 100")

    plt.xticks(list(k_values))

    plt.tight_layout()

    output_path = REPORTS_DIR / "elbow_plot.png"

    plt.savefig(
        output_path,
        dpi=160,
    )

    plt.close()

    print(f"Elbow plot created: " f"{output_path}")


# ---------------------------------------------------------------------
# CLUSTER NAMING
# ---------------------------------------------------------------------


def assign_cluster_names(
    feature_df,
    model,
):

    profile = feature_df.groupby("cluster_id")[FEATURES].mean()

    # Rank each cluster.
    roe_rank = profile["return_on_equity_pct"].rank(ascending=False)

    growth_rank = (
        profile["revenue_cagr_5yr"].rank(ascending=False)
        + profile["fcf_cagr_5yr"].rank(ascending=False)
    ) / 2

    debt_rank = profile["debt_to_equity"].rank(ascending=True)

    margin_rank = profile["operating_profit_margin_pct"].rank(ascending=False)

    names = {}

    # Strongest growth.
    growth_cluster = growth_rank.idxmin()

    names[growth_cluster] = "Growth Accelerator"

    # Lowest debt.
    debt_cluster = debt_rank.idxmin()

    if debt_cluster not in names:

        names[debt_cluster] = "Debt-Free Compounder"

    # Highest margins.
    margin_cluster = margin_rank.idxmin()

    if margin_cluster not in names:

        names[margin_cluster] = "High-Margin Quality"

    # Highest ROE.
    roe_cluster = roe_rank.idxmin()

    if roe_cluster not in names:

        names[roe_cluster] = "High-ROE Leader"

    # Remaining cluster.
    remaining = [cluster for cluster in profile.index if cluster not in names]

    if remaining:

        names[remaining[0]] = "Balanced Compounder"

    # Safety: ensure every cluster has a name.
    fallback_names = [
        "Balanced Compounder",
        "Value & Cash Flow",
        "Stable Core",
        "Emerging Compounder",
        "Turnaround Potential",
    ]

    used = set()

    for cluster_id in sorted(profile.index):

        current = names.get(cluster_id)

        if current is None or current in used:

            for fallback in fallback_names:

                if fallback not in used:

                    current = fallback
                    break

        names[cluster_id] = current

        used.add(current)

    return names, profile


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------


def run_clustering():

    print("=" * 70)
    print("SPRINT 6 - DAY 36")
    print("KMEANS CLUSTERING")
    print("=" * 70)

    # ---------------------------------------------------------------
    # 1. LOAD
    # ---------------------------------------------------------------

    print("\n[1/7] Loading data...")

    ratios = load_ratios()

    companies = load_companies()

    sectors = load_sectors()

    print(f"Companies loaded: " f"{len(companies)}")

    print(f"Sector mappings: " f"{len(sectors)}")

    # ---------------------------------------------------------------
    # 2. BUILD FEATURES
    # ---------------------------------------------------------------

    print("\n[2/7] Building feature matrix...")

    feature_df = build_feature_matrix(
        companies,
        sectors,
        ratios,
    )

    # Master company validation.
    company_ids = set(companies["id"])

    feature_ids = set(feature_df["company_id"])

    missing = company_ids - feature_ids

    if missing:

        raise RuntimeError(
            "Companies missing from " "clustering data: " + ", ".join(sorted(missing))
        )

    # Keep only master companies.
    feature_df = feature_df[feature_df["company_id"].isin(company_ids)].copy()

    # Exactly one row per company.
    feature_df = feature_df.sort_values("company_id").drop_duplicates(
        "company_id",
        keep="first",
    )

    print(f"Feature matrix companies: " f"{len(feature_df)}")

    # ---------------------------------------------------------------
    # 3. IMPUTE
    # ---------------------------------------------------------------

    print("\n[3/7] Sector-median imputation...")

    feature_df = impute_sector_medians(feature_df)

    # ---------------------------------------------------------------
    # 4. STANDARDIZE
    # ---------------------------------------------------------------

    print("\n[4/7] Standardizing features...")

    X = feature_df[FEATURES].astype(float).values

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(X)

    print(f"Scaled matrix shape: " f"{X_scaled.shape}")

    # ---------------------------------------------------------------
    # 5. ELBOW
    # ---------------------------------------------------------------

    print("\n[5/7] Creating elbow plot...")

    create_elbow_plot(X_scaled)

    # ---------------------------------------------------------------
    # 6. K-MEANS
    # ---------------------------------------------------------------

    print("\n[6/7] Running K-Means...")

    model = KMeans(
        n_clusters=5,
        random_state=42,
        n_init=20,
    )

    labels = model.fit_predict(X_scaled)

    feature_df["cluster_id"] = labels

    # Distance to assigned centroid.
    distances = model.transform(X_scaled)

    feature_df["distance_from_centroid"] = [
        distances[
            index,
            labels[index],
        ]
        for index in range(len(labels))
    ]

    # ---------------------------------------------------------------
    # 7. LABEL CLUSTERS
    # ---------------------------------------------------------------

    print("\n[7/7] Assigning cluster archetypes...")

    cluster_names, profile = assign_cluster_names(
        feature_df,
        model,
    )

    feature_df["cluster_name"] = feature_df["cluster_id"].map(cluster_names)

    # ---------------------------------------------------------------
    # OUTPUT
    # ---------------------------------------------------------------

    output = feature_df[
        [
            "company_id",
            "cluster_id",
            "cluster_name",
            "distance_from_centroid",
        ]
    ].copy()

    output = output.sort_values(
        [
            "cluster_id",
            "company_id",
        ]
    )

    output_path = OUTPUT_DIR / "cluster_labels.csv"

    output.to_csv(
        output_path,
        index=False,
    )

    # ---------------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------------

    print("\n")
    print("=" * 70)
    print("DAY 36 VALIDATION")
    print("=" * 70)

    print(f"Companies clustered : " f"{output['company_id'].nunique()}")

    print(f"Rows generated      : " f"{len(output)}")

    print(f"Cluster IDs         : " f"{sorted(output['cluster_id'].unique())}")

    print(f"Cluster count       : " f"{output['cluster_id'].nunique()}")

    print(f"Missing cluster IDs : " f"{output['cluster_id'].isna().sum()}")

    print(f"Duplicate companies : " f"{output['company_id'].duplicated().sum()}")

    print("\nCluster distribution:")

    distribution = (
        output.groupby(
            [
                "cluster_id",
                "cluster_name",
            ]
        )
        .size()
        .reset_index(name="companies")
        .sort_values("cluster_id")
    )

    print(distribution.to_string(index=False))

    print("\nCluster profiles:")

    profile_display = profile[FEATURES].round(2)

    print(profile_display.to_string())

    # ---------------------------------------------------------------
    # HARD GATES
    # ---------------------------------------------------------------

    assert len(output) == 92, f"Expected 92 rows, " f"got {len(output)}"

    assert output["company_id"].nunique() == 92

    assert output["cluster_id"].nunique() == 5

    assert output["cluster_id"].isin(range(5)).all()

    assert output["cluster_name"].notna().all()

    assert output["distance_from_centroid"].notna().all()

    assert output["company_id"].is_unique

    print("\n")
    print("=" * 70)
    print("DAY 36 COMPLETE - PASS")
    print("=" * 70)

    print("\nCreated:")

    print(f"  {output_path}")

    print(f"  {REPORTS_DIR / 'elbow_plot.png'}")

    print("\nRequired output columns:")

    print("  company_id")
    print("  cluster_id")
    print("  cluster_name")
    print("  distance_from_centroid")

    return output


if __name__ == "__main__":
    run_clustering()
