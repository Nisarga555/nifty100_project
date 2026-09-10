from pathlib import Path
import sqlite3
import re

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

DB_PATH = ROOT / "db" / "nifty100.sqlite3"
OUTPUT_PATH = ROOT / "output" / "peer_comparison.xlsx"

OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# REQUIRED PEER METRICS
# ============================================================

METRICS = [
    ("ROE", "roe"),
    ("ROCE", "roce"),
    ("NPM", "npm"),
    ("D/E", "de"),
    ("FCF", "fcf"),
    ("PAT CAGR 5Y", "pat_cagr_5yr"),
    ("Revenue CAGR 5Y", "revenue_cagr_5yr"),
    ("EPS CAGR 5Y", "eps_cagr_5yr"),
    ("ICR", "icr"),
    ("Asset Turnover", "asset_turnover"),
]


# ============================================================
# HELPERS
# ============================================================

def safe_sheet_name(name):
    """
    Excel worksheet names:
    - maximum 31 characters
    - cannot contain []:*?/\
    """

    name = str(name).strip()

    name = re.sub(
        r"[\[\]:*?/\\]",
        "_",
        name,
    )

    if not name:
        name = "Peer Group"

    return name[:31]


def parse_year(value):
    """
    Extract a four-digit year from:
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
        return np.nan

    return int(
        match.group(0)
    )


def numeric(value):
    return pd.to_numeric(
        value,
        errors="coerce",
    )


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

        peer_percentiles = pd.read_sql_query(
            """
            SELECT *
            FROM peer_percentiles
            """,
            connection,
        )

        ratios = pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            """,
            connection,
        )

    finally:

        connection.close()

    return (
        peer_percentiles,
        ratios,
    )


# ============================================================
# LOAD COMPANY NAMES
# ============================================================

def load_company_names():

    from src.screener.engine import (
        load_supporting_data
    )

    sources = load_supporting_data()

    companies = sources[
        "companies"
    ].copy()

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
            "Could not find company identifier "
            "in companies source."
        )

    result["company_id"] = (
        result["company_id"]
        .astype(str)
        .str.strip()
    )

    return result


# ============================================================
# LATEST RATIOS
# ============================================================

def latest_ratios(ratios):

    data = ratios.copy()

    data["parsed_year"] = (
        data["year"]
        .apply(parse_year)
    )

    data = data[
        data["parsed_year"].notna()
    ].copy()

    # Match screener annual selection.
    annual = data[
        ~data["year"]
        .astype(str)
        .str.contains(
            "09",
            na=False,
        )
    ].copy()

    if annual.empty:
        annual = data.copy()

    annual = annual.sort_values(
        [
            "company_id",
            "parsed_year",
            "year",
        ]
    )

    latest = (
        annual
        .groupby(
            "company_id",
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    latest = latest.drop(
        columns=["parsed_year"],
        errors="ignore",
    )

    return latest


# ============================================================
# BUILD PEER COMPARISON DATA
# ============================================================

def build_peer_comparison(
    peer_percentiles,
    ratios,
    companies,
):

    latest = latest_ratios(
        ratios
    )

    # --------------------------------------------------------
    # Latest composite score
    # --------------------------------------------------------

    composite = latest[
        [
            "company_id",
            "composite_quality_score",
        ]
    ].copy()

    composite["company_id"] = (
        composite["company_id"]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # Clean percentile source
    # --------------------------------------------------------

    data = peer_percentiles.copy()

    data["company_id"] = (
        data["company_id"]
        .astype(str)
        .str.strip()
    )

    data["metric"] = (
        data["metric"]
        .astype(str)
        .str.strip()
    )

    data["percentile_rank"] = pd.to_numeric(
        data["percentile_rank"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Values
    # --------------------------------------------------------

    values = data.pivot_table(
        index=[
            "peer_group_name",
            "company_id",
        ],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()

    values.columns.name = None

    # --------------------------------------------------------
    # Percentiles
    # --------------------------------------------------------

    percentiles = data.pivot_table(
        index=[
            "peer_group_name",
            "company_id",
        ],
        columns="metric",
        values="percentile_rank",
        aggfunc="first",
    ).reset_index()

    percentiles.columns.name = None

    # --------------------------------------------------------
    # Rename values
    # --------------------------------------------------------

    value_rename = {
        "roe": "ROE",
        "roce": "ROCE",
        "npm": "NPM",
        "de": "D/E",
        "fcf": "FCF",
        "pat_cagr_5yr": "PAT CAGR 5Y",
        "revenue_cagr_5yr": "Revenue CAGR 5Y",
        "eps_cagr_5yr": "EPS CAGR 5Y",
        "icr": "ICR",
        "asset_turnover": "Asset Turnover",
    }

    values = values.rename(
        columns=value_rename
    )

    # --------------------------------------------------------
    # Rename percentiles
    # --------------------------------------------------------

    percentile_rename = {
        "roe": "ROE Percentile",
        "roce": "ROCE Percentile",
        "npm": "NPM Percentile",
        "de": "D/E Percentile",
        "fcf": "FCF Percentile",
        "pat_cagr_5yr": "PAT CAGR 5Y Percentile",
        "revenue_cagr_5yr": "Revenue CAGR 5Y Percentile",
        "eps_cagr_5yr": "EPS CAGR 5Y Percentile",
        "icr": "ICR Percentile",
        "asset_turnover": "Asset Turnover Percentile",
    }

    percentiles = percentiles.rename(
        columns=percentile_rename
    )

    # --------------------------------------------------------
    # Merge values + percentiles
    # --------------------------------------------------------

    result = values.merge(
        percentiles,
        on=[
            "peer_group_name",
            "company_id",
        ],
        how="outer",
    )

    # --------------------------------------------------------
    # Company names
    # --------------------------------------------------------

    result = result.merge(
        companies,
        on="company_id",
        how="left",
    )

    # --------------------------------------------------------
    # Composite
    # --------------------------------------------------------

    result = result.merge(
        composite,
        on="company_id",
        how="left",
    )

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    value_columns = [
        "ROE",
        "ROCE",
        "NPM",
        "D/E",
        "FCF",
        "PAT CAGR 5Y",
        "Revenue CAGR 5Y",
        "EPS CAGR 5Y",
        "ICR",
        "Asset Turnover",
    ]

    percentile_columns = [
        "ROE Percentile",
        "ROCE Percentile",
        "NPM Percentile",
        "D/E Percentile",
        "FCF Percentile",
        "PAT CAGR 5Y Percentile",
        "Revenue CAGR 5Y Percentile",
        "EPS CAGR 5Y Percentile",
        "ICR Percentile",
        "Asset Turnover Percentile",
    ]

    final_columns = [
        "peer_group_name",
        "company_id",
        "company_name",
    ]

    for column in value_columns:

        if column in result.columns:

            final_columns.append(
                column
            )

    for column in percentile_columns:

        if column in result.columns:

            final_columns.append(
                column
            )

    if (
        "composite_quality_score"
        in result.columns
    ):

        final_columns.append(
            "composite_quality_score"
        )

    result = result[
        final_columns
    ].copy()

    result = result.rename(
        columns={
            "composite_quality_score":
            "Composite Score"
        }
    )

    return result


# ============================================================
# WRITE WORKBOOK
# ============================================================

def write_workbook(data):

    if OUTPUT_PATH.exists():

        OUTPUT_PATH.unlink()

    peer_groups = sorted(
        data[
            "peer_group_name"
        ]
        .dropna()
        .astype(str)
        .unique()
    )

    with pd.ExcelWriter(
        OUTPUT_PATH,
        engine="openpyxl",
    ) as writer:

        for peer_group in peer_groups:

            group = data[
                data[
                    "peer_group_name"
                ].astype(str)
                == peer_group
            ].copy()

            group = group.sort_values(
                "company_name",
                na_position="last",
            )

            sheet_name = safe_sheet_name(
                peer_group
            )

            group.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )


# ============================================================
# FORMAT WORKBOOK
# ============================================================

def format_workbook(data):

    workbook = load_workbook(
        OUTPUT_PATH
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    header_font = Font(
        bold=True,
        color="FFFFFF",
    )

    # --------------------------------------------------------
    # Percentile fills
    # --------------------------------------------------------

    green_fill = PatternFill(
        fill_type="solid",
        fgColor="C6EFCE",
    )

    yellow_fill = PatternFill(
        fill_type="solid",
        fgColor="FFEB9C",
    )

    red_fill = PatternFill(
        fill_type="solid",
        fgColor="FFC7CE",
    )

    # --------------------------------------------------------
    # Benchmark row
    # --------------------------------------------------------

    benchmark_fill = PatternFill(
        fill_type="solid",
        fgColor="FFD966",
    )

    # --------------------------------------------------------
    # Format every worksheet
    # --------------------------------------------------------

    for worksheet in workbook.worksheets:

        max_row = worksheet.max_row
        max_column = worksheet.max_column

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        for cell in worksheet[1]:

            cell.fill = header_fill

            cell.font = header_font

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        worksheet.freeze_panes = "D2"

        worksheet.auto_filter.ref = (
            worksheet.dimensions
        )

        # ----------------------------------------------------
        # Header lookup
        # ----------------------------------------------------

        headers = {}

        for column_number in range(
            1,
            max_column + 1,
        ):

            header = worksheet.cell(
                row=1,
                column=column_number,
            ).value

            if header is not None:

                headers[
                    str(header)
                ] = column_number

        # ----------------------------------------------------
        # Percentile formatting
        # ----------------------------------------------------

        for row_number in range(
            2,
            max_row + 1,
        ):

            for header, column_number in (
                headers.items()
            ):

                if "Percentile" not in header:
                    continue

                cell = worksheet.cell(
                    row=row_number,
                    column=column_number,
                )

                value = numeric(
                    cell.value
                )

                if pd.isna(value):
                    continue

                if value >= 75:

                    cell.fill = green_fill

                elif value <= 25:

                    cell.fill = red_fill

                else:

                    cell.fill = yellow_fill

                cell.number_format = "0.0"

        # ----------------------------------------------------
        # Number formatting
        # ----------------------------------------------------

        for row_number in range(
            2,
            max_row + 1,
        ):

            for column_number in range(
                1,
                max_column + 1,
            ):

                cell = worksheet.cell(
                    row=row_number,
                    column=column_number,
                )

                header = worksheet.cell(
                    row=1,
                    column=column_number,
                ).value

                if header is None:
                    continue

                header = str(header)

                if not isinstance(
                    cell.value,
                    (int, float),
                ):
                    continue

                if header == "FCF":

                    cell.number_format = (
                        "#,##0.00"
                    )

                elif header == "Composite Score":

                    cell.number_format = (
                        "0.00"
                    )

                elif (
                    "Percentile" in header
                    or "CAGR" in header
                    or header in [
                        "ROE",
                        "ROCE",
                        "NPM",
                        "D/E",
                        "ICR",
                        "Asset Turnover",
                    ]
                ):

                    cell.number_format = (
                        "0.00"
                    )

        # ----------------------------------------------------
        # Column widths
        # ----------------------------------------------------

        for column_number in range(
            1,
            max_column + 1,
        ):

            column_letter = (
                get_column_letter(
                    column_number
                )
            )

            maximum_length = 0

            for cell in worksheet[
                column_letter
            ]:

                try:

                    maximum_length = max(
                        maximum_length,
                        len(
                            str(
                                cell.value
                            )
                        ),
                    )

                except Exception:
                    pass

            worksheet.column_dimensions[
                column_letter
            ].width = min(
                maximum_length + 2,
                30,
            )

        # ----------------------------------------------------
        # Alignment
        # ----------------------------------------------------

        for row in worksheet.iter_rows():

            for cell in row:

                cell.alignment = Alignment(
                    vertical="center"
                )

        # ----------------------------------------------------
        # Add peer median / benchmark row
        # ----------------------------------------------------

        # Find numeric metric columns.
        numeric_headers = []

        for header, column_number in (
            headers.items()
        ):

            if header in [
                "ROE",
                "ROCE",
                "NPM",
                "D/E",
                "FCF",
                "PAT CAGR 5Y",
                "Revenue CAGR 5Y",
                "EPS CAGR 5Y",
                "ICR",
                "Asset Turnover",
                "ROE Percentile",
                "ROCE Percentile",
                "NPM Percentile",
                "D/E Percentile",
                "FCF Percentile",
                "PAT CAGR 5Y Percentile",
                "Revenue CAGR 5Y Percentile",
                "EPS CAGR 5Y Percentile",
                "ICR Percentile",
                "Asset Turnover Percentile",
                "Composite Score",
            ]:

                numeric_headers.append(
                    (
                        header,
                        column_number,
                    )
                )

        median_row = (
            worksheet.max_row + 2
        )

        worksheet.cell(
            row=median_row,
            column=1,
        ).value = "Peer Median"

        worksheet.cell(
            row=median_row,
            column=1,
        ).fill = benchmark_fill

        worksheet.cell(
            row=median_row,
            column=1,
        ).font = Font(
            bold=True
        )

        # ----------------------------------------------------
        # Calculate median for every numeric column
        # ----------------------------------------------------

        for header, column_number in (
            numeric_headers
        ):

            values = []

            for row_number in range(
                2,
                worksheet.max_row + 1,
            ):

                # Don't include the median row itself.
                if row_number >= median_row:
                    continue

                value = numeric(
                    worksheet.cell(
                        row=row_number,
                        column=column_number,
                    ).value
                )

                if not pd.isna(value):
                    values.append(
                        value
                    )

            if values:

                median_value = float(
                    np.median(
                        values
                    )
                )

                cell = worksheet.cell(
                    row=median_row,
                    column=column_number,
                )

                cell.value = median_value
                cell.fill = benchmark_fill
                cell.font = Font(
                    bold=True
                )

                if header == "FCF":

                    cell.number_format = (
                        "#,##0.00"
                    )

                else:

                    cell.number_format = (
                        "0.00"
                    )

        # ----------------------------------------------------
        # Add benchmark label for company group
        # ----------------------------------------------------

        if "company_name" in headers:

            name_column = headers[
                "company_name"
            ]

            worksheet.cell(
                row=median_row,
                column=name_column,
            ).value = (
                "Peer Median / Benchmark"
            )

            worksheet.cell(
                row=median_row,
                column=name_column,
            ).fill = benchmark_fill

            worksheet.cell(
                row=median_row,
                column=name_column,
            ).font = Font(
                bold=True
            )

    workbook.save(
        OUTPUT_PATH
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_workbook():

    workbook = load_workbook(
        OUTPUT_PATH,
        read_only=True,
    )

    sheets = workbook.sheetnames

    print()
    print("=" * 70)
    print("DAY 20 VALIDATION")
    print("=" * 70)

    print(
        f"Workbook:\n{OUTPUT_PATH}"
    )

    print(
        f"Sheets: {len(sheets)}"
    )

    total_companies = 0

    for sheet in sheets:

        worksheet = workbook[
            sheet
        ]

        # Subtract header + median row.
        company_count = max(
            0,
            worksheet.max_row - 2,
        )

        total_companies += (
            company_count
        )

        print(
            f"{sheet:<30}"
            f"{company_count:>4} companies"
        )

    print()
    print(
        f"Total peer companies: "
        f"{total_companies}"
    )

    if len(sheets) == 11:

        print(
            "PASS: Exactly 11 peer-group sheets"
        )

    else:

        print(
            "FAIL: Expected exactly 11 sheets"
        )

    if total_companies == 56:

        print(
            "PASS: 56 peer-assigned companies represented"
        )

    else:

        print(
            "WARNING: Expected 56 peer-assigned companies"
        )

    workbook.close()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("DAY 20 - PEER COMPARISON WORKBOOK")
    print("=" * 70)

    peer_percentiles, ratios = (
        load_sqlite_data()
    )

    print(
        f"Peer percentile rows: "
        f"{len(peer_percentiles)}"
    )

    print(
        f"Financial ratio rows: "
        f"{len(ratios)}"
    )

    companies = (
        load_company_names()
    )

    print(
        f"Company master rows: "
        f"{len(companies)}"
    )

    comparison = (
        build_peer_comparison(
            peer_percentiles,
            ratios,
            companies,
        )
    )

    print(
        f"Peer comparison rows: "
        f"{len(comparison)}"
    )

    print(
        f"Peer groups: "
        f"{comparison['peer_group_name'].nunique()}"
    )

    write_workbook(
        comparison
    )

    format_workbook(
        comparison
    )

    print()
    print(
        "Workbook created successfully."
    )

    validate_workbook()


if __name__ == "__main__":
    main()