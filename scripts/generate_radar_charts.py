from pathlib import Path
import re
import sqlite3

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "db" / "nifty100.sqlite3"
OUTPUT_DIR = ROOT / "reports" / "radar_charts"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# RADAR CONFIGURATION
# ============================================================

RADAR_LABELS = [
    "ROE",
    "ROCE",
    "NPM",
    "D/E",
    "FCF Score",
    "PAT CAGR 5Y",
    "Revenue CAGR 5Y",
    "Composite Score",
]


# ============================================================
# YEAR PARSER
# ============================================================

def parse_year(value):
    """
    Extract a four-digit year.

    Examples:
        2024
        2024-03
        Mar 2024
        Sep 2024
    """

    match = re.search(
        r"(19|20)\d{2}",
        str(value),
    )

    if not match:
        return None

    return int(
        match.group(0)
    )


# ============================================================
# SAFE FILENAME
# ============================================================

def safe_filename(name):
    """
    Create a Windows-safe filename.
    """

    name = str(name).strip()

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name,
    )

    name = re.sub(
        r"\s+",
        "_",
        name,
    )

    return name


# ============================================================
# PERCENTILE HELPERS
# ============================================================

def percent_rank(series):
    """
    Convert a numeric series to 0-100 percentile scores.

    Higher value = higher score.
    """

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float,
    )

    valid = numeric.dropna()

    if valid.empty:
        return result

    result.loc[valid.index] = (
        valid.rank(
            method="average",
            pct=True,
        ) * 100
    )

    return result


def inverse_percent_rank(series):
    """
    Lower value = better score.

    Used for D/E.
    """

    direct = percent_rank(
        series
    )

    result = direct.copy()

    valid = result.notna()

    result.loc[valid] = (
        100 - result.loc[valid]
    )

    return result


# ============================================================
# LOAD SQLITE DATA
# ============================================================

def load_sqlite_data():

    if not DB_PATH.exists():

        raise FileNotFoundError(
            f"SQLite database not found:\n{DB_PATH}"
        )

    connection = sqlite3.connect(
        DB_PATH
    )

    try:

        ratios = pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            """,
            connection,
        )

        peer_percentiles = pd.read_sql_query(
            """
            SELECT *
            FROM peer_percentiles
            """,
            connection,
        )

    finally:

        connection.close()

    return (
        ratios,
        peer_percentiles,
    )


# ============================================================
# LOAD COMPANY MASTER
# ============================================================

def load_company_master():

    from src.screener.engine import (
        load_supporting_data
    )

    sources = load_supporting_data()

    companies = sources[
        "companies"
    ].copy()

    # --------------------------------------------------------
    # Normalized loader may expose company_id
    # --------------------------------------------------------

    if "company_id" in companies.columns:

        result = companies[
            [
                "company_id",
                "company_name",
            ]
        ].copy()

    elif "id" in companies.columns:

        result = companies[
            [
                "id",
                "company_name",
            ]
        ].copy()

        result = result.rename(
            columns={
                "id": "company_id"
            }
        )

    else:

        raise RuntimeError(
            "Companies source does not contain "
            "'company_id' or 'id'."
        )

    result["company_id"] = (
        result["company_id"]
        .astype(str)
        .str.strip()
    )

    result["company_name"] = (
        result["company_name"]
        .astype(str)
        .str.strip()
    )

    return result


# ============================================================
# LATEST RATIO ROW
# ============================================================

def latest_ratio_per_company(ratios):
    """
    Select the latest available ratio row for EVERY company.

    IMPORTANT:
    We intentionally do not exclude September rows here.

    The database has validated ratio coverage for all 92
    companies, so radar coverage must preserve all 92.
    """

    data = ratios.copy()

    data["parsed_year"] = (
        data["year"].apply(
            parse_year
        )
    )

    data = data[
        data["parsed_year"].notna()
    ].copy()

    data["company_id"] = (
        data["company_id"]
        .astype(str)
        .str.strip()
    )

    data = data.sort_values(
        [
            "company_id",
            "parsed_year",
            "year",
        ]
    )

    latest = (
        data
        .groupby(
            "company_id",
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    latest = latest.drop(
        columns=[
            "parsed_year"
        ],
        errors="ignore",
    )

    return latest


# ============================================================
# BUILD FULL NIFTY 100 SCORES
# ============================================================

def build_full_universe_scores(
    latest
):
    """
    Create 0-100 scores across the complete latest-company
    universe.

    These are used for companies without an assigned peer group.
    """

    data = latest.copy()

    scores = pd.DataFrame(
        index=data.index
    )

    # --------------------------------------------------------
    # ROE
    # --------------------------------------------------------

    scores["ROE"] = percent_rank(
        data[
            "return_on_equity_pct"
        ]
    )

    # --------------------------------------------------------
    # ROCE
    # --------------------------------------------------------

    scores["ROCE"] = percent_rank(
        data[
            "return_on_capital_employed_pct"
        ]
    )

    # --------------------------------------------------------
    # NPM
    # --------------------------------------------------------

    scores["NPM"] = percent_rank(
        data[
            "net_profit_margin_pct"
        ]
    )

    # --------------------------------------------------------
    # D/E
    # --------------------------------------------------------

    scores["D/E"] = inverse_percent_rank(
        data[
            "debt_to_equity"
        ]
    )

    # --------------------------------------------------------
    # FCF
    # --------------------------------------------------------

    scores["FCF Score"] = percent_rank(
        data[
            "free_cash_flow_cr"
        ]
    )

    # --------------------------------------------------------
    # PAT CAGR
    # --------------------------------------------------------

    scores["PAT CAGR 5Y"] = percent_rank(
        data[
            "pat_cagr_5yr"
        ]
    )

    # --------------------------------------------------------
    # Revenue CAGR
    # --------------------------------------------------------

    scores["Revenue CAGR 5Y"] = percent_rank(
        data[
            "revenue_cagr_5yr"
        ]
    )

    # --------------------------------------------------------
    # Composite
    # --------------------------------------------------------

    scores["Composite Score"] = pd.to_numeric(
        data[
            "composite_quality_score"
        ],
        errors="coerce",
    ).clip(
        0,
        100,
    )

    scores["company_id"] = (
        data["company_id"]
        .astype(str)
        .str.strip()
    )

    return scores


# ============================================================
# BUILD PEER LOOKUP
# ============================================================

def build_peer_lookup(
    peer_percentiles
):
    """
    Create:

        (company_id, peer_group) ->
        {metric: percentile}
    """

    lookup = {}

    if peer_percentiles.empty:
        return lookup

    required_columns = {
        "company_id",
        "peer_group_name",
        "metric",
        "percentile_rank",
    }

    missing = (
        required_columns
        - set(
            peer_percentiles.columns
        )
    )

    if missing:

        raise RuntimeError(
            "peer_percentiles missing columns: "
            f"{sorted(missing)}"
        )

    for _, row in (
        peer_percentiles.iterrows()
    ):

        company_id = str(
            row["company_id"]
        ).strip()

        peer_group = str(
            row["peer_group_name"]
        ).strip()

        metric = str(
            row["metric"]
        ).strip()

        percentile = pd.to_numeric(
            row["percentile_rank"],
            errors="coerce",
        )

        key = (
            company_id,
            peer_group,
        )

        if key not in lookup:
            lookup[key] = {}

        lookup[key][
            metric
        ] = percentile

    return lookup


# ============================================================
# PEER GROUP MAPPING
# ============================================================

def build_peer_group_mapping(
    peer_percentiles
):
    """
    Map company_id -> peer group.
    """

    mapping = {}

    if peer_percentiles.empty:
        return mapping

    rows = (
        peer_percentiles[
            [
                "company_id",
                "peer_group_name",
            ]
        ]
        .drop_duplicates()
    )

    for _, row in rows.iterrows():

        company_id = str(
            row["company_id"]
        ).strip()

        peer_group = str(
            row["peer_group_name"]
        ).strip()

        mapping[
            company_id
        ] = peer_group

    return mapping


# ============================================================
# GET COMPANY RADAR VALUES
# ============================================================

def get_company_radar_values(
    company_id,
    peer_group,
    peer_lookup,
    full_scores,
):
    """
    Return the eight radar values.

    Assigned peer:
        first seven axes use peer percentiles.
        Composite uses actual composite score.

    No peer:
        use NIFTY 100 percentile scores.
    """

    company_id = str(
        company_id
    ).strip()

    # ========================================================
    # PEER-GROUP COMPANY
    # ========================================================

    if (
        peer_group
        and peer_group
        != "No peer group assigned"
    ):

        key = (
            company_id,
            str(peer_group),
        )

        peer_values = peer_lookup.get(
            key
        )

        if peer_values:

            values = [
                peer_values.get(
                    "roe",
                    np.nan,
                ),

                peer_values.get(
                    "roce",
                    np.nan,
                ),

                peer_values.get(
                    "npm",
                    np.nan,
                ),

                peer_values.get(
                    "de",
                    np.nan,
                ),

                peer_values.get(
                    "fcf",
                    np.nan,
                ),

                peer_values.get(
                    "pat_cagr_5yr",
                    np.nan,
                ),

                peer_values.get(
                    "revenue_cagr_5yr",
                    np.nan,
                ),
            ]

            composite_row = (
                full_scores[
                    full_scores[
                        "company_id"
                    ] == company_id
                ]
            )

            if composite_row.empty:

                values.append(
                    np.nan
                )

            else:

                values.append(
                    composite_row.iloc[0][
                        "Composite Score"
                    ]
                )

            return values

    # ========================================================
    # NO PEER GROUP
    # ========================================================

    company_row = (
        full_scores[
            full_scores[
                "company_id"
            ] == company_id
        ]
    )

    if company_row.empty:
        return None

    row = company_row.iloc[0]

    return [
        row["ROE"],
        row["ROCE"],
        row["NPM"],
        row["D/E"],
        row["FCF Score"],
        row["PAT CAGR 5Y"],
        row["Revenue CAGR 5Y"],
        row["Composite Score"],
    ]


# ============================================================
# CALCULATE PEER AVERAGE
# ============================================================

def calculate_peer_average(
    peer_group,
    peer_lookup,
    full_scores,
):
    """
    Calculate peer-group average radar values.

    Returns None when the peer group has no usable values.
    """

    if (
        not peer_group
        or peer_group
        == "No peer group assigned"
    ):
        return None

    peer_group = str(
        peer_group
    ).strip()

    company_ids = set()

    for (
        company_id,
        group,
    ) in peer_lookup.keys():

        if (
            str(group).strip()
            == peer_group
        ):

            company_ids.add(
                str(company_id).strip()
            )

    if not company_ids:
        return None

    rows = []

    for company_id in sorted(
        company_ids
    ):

        values = (
            get_company_radar_values(
                company_id,
                peer_group,
                peer_lookup,
                full_scores,
            )
        )

        if values is not None:

            numeric_values = pd.to_numeric(
                pd.Series(values),
                errors="coerce",
            )

            if numeric_values.notna().any():

                rows.append(
                    numeric_values.tolist()
                )

    if not rows:
        return None

    array = np.array(
        rows,
        dtype=float,
    )

    # Avoid "Mean of empty slice" warnings.
    result = []

    for column in range(
        array.shape[1]
    ):

        valid = array[
            ~np.isnan(
                array[:, column]
            ),
            column,
        ]

        if len(valid) == 0:

            result.append(
                np.nan
            )

        else:

            result.append(
                float(
                    np.mean(valid)
                )
            )

    return result


# ============================================================
# CREATE RADAR CHART
# ============================================================

def create_radar_chart(
    company_name,
    peer_group,
    company_values,
    reference_values,
    reference_label,
    output_path,
):
    """
    Create one eight-axis radar chart.
    """

    company_values = np.array(
        company_values,
        dtype=float,
    )

    company_values = np.nan_to_num(
        company_values,
        nan=0.0,
        posinf=100.0,
        neginf=0.0,
    )

    reference = None

    if reference_values is not None:

        reference = np.array(
            reference_values,
            dtype=float,
        )

        reference = np.nan_to_num(
            reference,
            nan=0.0,
            posinf=100.0,
            neginf=0.0,
        )

    number_of_axes = len(
        RADAR_LABELS
    )

    angles = np.linspace(
        0,
        2 * np.pi,
        number_of_axes,
        endpoint=False,
    )

    closed_angles = np.concatenate(
        [
            angles,
            [angles[0]],
        ]
    )

    closed_company_values = np.concatenate(
        [
            company_values,
            [company_values[0]],
        ]
    )

    figure = plt.figure(
        figsize=(9, 9)
    )

    axis = figure.add_subplot(
        111,
        polar=True,
    )

    # ========================================================
    # COMPANY POLYGON
    # ========================================================

    axis.plot(
        closed_angles,
        closed_company_values,
        linewidth=2.5,
        label=company_name,
    )

    axis.fill(
        closed_angles,
        closed_company_values,
        alpha=0.20,
    )

    # ========================================================
    # REFERENCE POLYGON
    # ========================================================

    if reference is not None:

        closed_reference = np.concatenate(
            [
                reference,
                [reference[0]],
            ]
        )

        axis.plot(
            closed_angles,
            closed_reference,
            linestyle="--",
            linewidth=2,
            label=reference_label,
        )

    # ========================================================
    # AXES
    # ========================================================

    axis.set_xticks(
        angles
    )

    axis.set_xticklabels(
        RADAR_LABELS,
        fontsize=10,
    )

    axis.set_ylim(
        0,
        100,
    )

    axis.set_yticks(
        [
            20,
            40,
            60,
            80,
            100,
        ]
    )

    axis.set_yticklabels(
        [
            "20",
            "40",
            "60",
            "80",
            "100",
        ],
        fontsize=8,
    )

    axis.set_title(
        f"{company_name}\n"
        f"Peer Group: {peer_group}",
        fontsize=14,
        fontweight="bold",
        pad=25,
    )

    axis.grid(
        True
    )

    axis.legend(
        loc="upper right",
        bbox_to_anchor=(
            1.32,
            1.15,
        ),
    )

    figure.tight_layout()

    figure.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DAY 19 - RADAR CHART GENERATOR")
    print("=" * 70)

    # ========================================================
    # LOAD DATABASE
    # ========================================================

    ratios, peer_percentiles = (
        load_sqlite_data()
    )

    print(
        f"Financial ratio rows: "
        f"{len(ratios)}"
    )

    print(
        f"Peer percentile rows: "
        f"{len(peer_percentiles)}"
    )

    # ========================================================
    # LATEST ROW FOR ALL COMPANIES
    # ========================================================

    latest = (
        latest_ratio_per_company(
            ratios
        )
    )

    print(
        f"Latest company rows: "
        f"{len(latest)}"
    )

    # ========================================================
    # COMPANY MASTER
    # ========================================================

    companies = (
        load_company_master()
    )

    print(
        f"Company master rows: "
        f"{len(companies)}"
    )

    # ========================================================
    # ENSURE ALL COMPANY IDs ARE STRINGS
    # ========================================================

    latest["company_id"] = (
        latest["company_id"]
        .astype(str)
        .str.strip()
    )

    companies["company_id"] = (
        companies["company_id"]
        .astype(str)
        .str.strip()
    )

    # ========================================================
    # BUILD FULL UNIVERSE SCORES
    # ========================================================

    full_scores = (
        build_full_universe_scores(
            latest
        )
    )

    # ========================================================
    # PEER LOOKUP
    # ========================================================

    peer_lookup = (
        build_peer_lookup(
            peer_percentiles
        )
    )

    peer_groups = (
        build_peer_group_mapping(
            peer_percentiles
        )
    )

    # ========================================================
    # GENERATION COUNTERS
    # ========================================================

    generated = 0
    peer_charts = 0
    standalone_charts = 0
    failed = 0

    generated_ids = set()

    # ========================================================
    # IMPORTANT:
    #
    # Use the 92-company MASTER as the iteration universe.
    #
    # If a company has a ratio row, create its radar.
    # If it somehow does not, log it instead of inventing data.
    # ========================================================

    for _, company in (
        companies.iterrows()
    ):

        company_id = str(
            company["company_id"]
        ).strip()

        company_name = str(
            company["company_name"]
        ).strip()

        if (
            not company_name
            or company_name.lower()
            == "nan"
        ):

            company_name = company_id

        # ----------------------------------------------------
        # Find latest ratio row
        # ----------------------------------------------------

        company_rows = latest[
            latest[
                "company_id"
            ] == company_id
        ]

        if company_rows.empty:

            print(
                f"WARNING: No latest ratio row "
                f"for {company_name}"
            )

            failed += 1
            continue

        # ----------------------------------------------------
        # Peer group
        # ----------------------------------------------------

        peer_group = peer_groups.get(
            company_id,
            "No peer group assigned",
        )

        # ----------------------------------------------------
        # Company radar values
        # ----------------------------------------------------

        company_values = (
            get_company_radar_values(
                company_id,
                peer_group,
                peer_lookup,
                full_scores,
            )
        )

        if company_values is None:

            print(
                f"WARNING: Could not create "
                f"radar values for {company_name}"
            )

            failed += 1
            continue

        # ----------------------------------------------------
        # Reference
        # ----------------------------------------------------

        if (
            peer_group
            == "No peer group assigned"
        ):

            reference_values = (
                full_scores[
                    RADAR_LABELS
                ]
                .mean(
                    numeric_only=True
                )
                .tolist()
            )

            reference_label = (
                "NIFTY 100 Average"
            )

            standalone_charts += 1

        else:

            reference_values = (
                calculate_peer_average(
                    peer_group,
                    peer_lookup,
                    full_scores,
                )
            )

            reference_label = (
                f"{peer_group} Average"
            )

            peer_charts += 1

        # ----------------------------------------------------
        # Output path
        # ----------------------------------------------------

        filename = (
            f"{safe_filename(company_name)}"
            f"_radar.png"
        )

        output_path = (
            OUTPUT_DIR / filename
        )

        # ----------------------------------------------------
        # Create
        # ----------------------------------------------------

        create_radar_chart(
            company_name=company_name,
            peer_group=peer_group,
            company_values=company_values,
            reference_values=reference_values,
            reference_label=reference_label,
            output_path=output_path,
        )

        generated += 1

        generated_ids.add(
            company_id
        )

        print(
            f"[{generated:02d}] "
            f"{company_name:<30} "
            f"| {peer_group}"
        )

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    png_files = list(
        OUTPUT_DIR.glob(
            "*.png"
        )
    )

    print()
    print("=" * 70)
    print("DAY 19 VALIDATION")
    print("=" * 70)

    print(
        f"Master companies:       "
        f"{len(companies)}"
    )

    print(
        f"Latest ratio companies: "
        f"{len(latest)}"
    )

    print(
        f"Charts generated:       "
        f"{generated}"
    )

    print(
        f"PNG files found:         "
        f"{len(png_files)}"
    )

    print(
        f"Peer-group charts:       "
        f"{peer_charts}"
    )

    print(
        f"Standalone charts:      "
        f"{standalone_charts}"
    )

    print(
        f"Failed charts:           "
        f"{failed}"
    )

    # --------------------------------------------------------
    # Coverage
    # --------------------------------------------------------

    if generated == len(companies):

        print(
            "PASS: Radar coverage = "
            f"{generated}/{len(companies)}"
        )

    else:

        missing = (
            set(
                companies[
                    "company_id"
                ]
                .astype(str)
            )
            - generated_ids
        )

        print(
            "WARNING: Missing radar charts:"
        )

        print(
            sorted(missing)
        )

    # --------------------------------------------------------
    # Expected peer/standalone split
    # --------------------------------------------------------

    print()

    print(
        f"Peer + standalone = "
        f"{peer_charts} + "
        f"{standalone_charts} = "
        f"{peer_charts + standalone_charts}"
    )

    if (
        peer_charts
        + standalone_charts
        == generated
    ):

        print(
            "PASS: Chart classification is consistent"
        )

    else:

        print(
            "WARNING: Chart classification mismatch"
        )

    # --------------------------------------------------------
    # PNG check
    # --------------------------------------------------------

    if len(png_files) == generated:

        print(
            "PASS: PNG count matches generated charts"
        )

    elif len(png_files) > generated:

        print(
            "WARNING: Existing PNG files from "
            "previous runs are present"
        )

    else:

        print(
            "FAIL: Fewer PNG files than generated charts"
        )

    print()
    print(
        f"Output directory:\n"
        f"{OUTPUT_DIR}"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()