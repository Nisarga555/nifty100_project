"""
NIFTY 100 - Sprint 3 Screener Engine
Day 15 - Filter Engine Core

Responsibilities:
    1. Load financial ratios from SQLite.
    2. Load raw Excel sources safely.
    3. Detect title/header rows in Excel files.
    4. Normalize company identifiers.
    5. Build latest usable annual company dataset.
    6. Apply configurable screener filters.
    7. Support Financial-sector D/E exemption.
    8. Support Debt-Free ICR treatment.
    9. Support custom filters.
"""

from __future__ import annotations

import operator
import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.screener.scoring import calculate_composite_quality_score

# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "db" / "nifty100.sqlite3"

CONFIG_PATH = PROJECT_ROOT / "config" / "screener_config.yaml"

RAW_DIR = PROJECT_ROOT / "data" / "raw"


# ============================================================
# OPERATORS
# ============================================================

OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


# ============================================================
# COLUMN CLEANING
# ============================================================


def clean_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize column names.

    Example:
        Company ID
        company_id
        Company Name

    become:
        company_id
        company_id
        company_name
    """

    result = dataframe.copy()

    cleaned = []

    for column in result.columns:

        value = str(column).strip().lower()

        value = re.sub(
            r"[^a-z0-9]+",
            "_",
            value,
        )

        value = value.strip("_")

        cleaned.append(value)

    result.columns = cleaned

    return result


# ============================================================
# HEADER DETECTION
# ============================================================


def detect_header_row(
    filename: str,
) -> int:
    """
    Detect the real header row in raw Excel files.

    Some source workbooks contain a title row such as:

        MKT Fintech — Nifty 100 | Companies | 92 Records

    followed by the real header.

    We inspect the first several rows and look for known
    financial/source column names.
    """

    path = RAW_DIR / filename

    if not path.exists():

        raise FileNotFoundError(f"Excel source not found: {path}")

    preview = pd.read_excel(
        path,
        header=None,
        nrows=12,
    )

    known_tokens = {
        "id",
        "company_id",
        "company_name",
        "year",
        "sales",
        "net_profit",
        "borrowings",
        "operating_profit",
        "broad_sector",
        "sub_sector",
        "market_cap_crore",
        "date",
        "eps",
    }

    best_row = 0
    best_score = -1

    for row_index in range(len(preview)):

        values = [
            str(value).strip().lower()
            for value in preview.iloc[row_index].tolist()
            if not pd.isna(value)
        ]

        score = 0

        for value in values:

            normalized = re.sub(
                r"[^a-z0-9]+",
                "_",
                value,
            ).strip("_")

            if normalized in known_tokens:
                score += 1

        if score > best_score:

            best_score = score
            best_row = row_index

    # If no recognizable header was found,
    # default to the first row.
    if best_score <= 0:
        return 0

    return best_row


# ============================================================
# EXCEL LOADER
# ============================================================


def load_excel_source(
    filename: str,
) -> pd.DataFrame:
    """
    Load an Excel source using automatic header detection.
    """

    path = RAW_DIR / filename

    if not path.exists():

        raise FileNotFoundError(f"Required source file not found: {path}")

    header_row = detect_header_row(filename)

    dataframe = pd.read_excel(
        path,
        header=header_row,
    )

    dataframe = clean_columns(dataframe)

    # Remove completely empty rows.
    dataframe = dataframe.dropna(how="all").reset_index(drop=True)

    return dataframe


# ============================================================
# COMPANY ID NORMALIZATION
# ============================================================


def normalize_company_id_column(
    dataframe: pd.DataFrame,
    required: bool = True,
) -> pd.DataFrame:
    """
    Normalize source identifiers.

    Source files may use:
        id
        company_id

    Internal screener representation:
        company_id
    """

    result = clean_columns(dataframe)

    if "company_id" not in result.columns:

        if "id" in result.columns:

            result = result.rename(columns={"id": "company_id"})

    if "company_id" not in result.columns:

        if required:

            raise ValueError(
                "Source dataframe does not contain "
                "'company_id' or 'id'. "
                f"Available columns: "
                f"{list(result.columns)}"
            )

        return result

    result["company_id"] = result["company_id"].astype(str).str.strip()

    return result


# ============================================================
# YEAR PARSER
# ============================================================


def year_number(
    value: Any,
) -> int | None:
    """
    Extract four-digit year.

    Supports:
        2024
        2024-03
        Mar 2024
        2024-09
    """

    if pd.isna(value):
        return None

    text = str(value)

    match = re.search(
        r"(19|20)\d{2}",
        text,
    )

    if not match:
        return None

    return int(match.group(0))


# ============================================================
# CONFIGURATION
# ============================================================


def load_config(
    config_path: Path = CONFIG_PATH,
) -> dict[str, Any]:

    if not config_path.exists():

        raise FileNotFoundError(f"Screener configuration not found: " f"{config_path}")

    with open(
        config_path,
        "r",
        encoding="utf-8",
    ) as file:

        config = yaml.safe_load(file)

    if not isinstance(
        config,
        dict,
    ):

        raise ValueError("Screener configuration must be a YAML mapping.")

    return config


# ============================================================
# SQLITE RATIO LOADER
# ============================================================


def load_ratio_data(
    db_path: Path = DB_PATH,
) -> pd.DataFrame:

    if not db_path.exists():

        raise FileNotFoundError(f"SQLite database not found: " f"{db_path}")

    connection = sqlite3.connect(db_path)

    try:

        dataframe = pd.read_sql_query(
            """
            SELECT *
            FROM financial_ratios
            """,
            connection,
        )

    finally:

        connection.close()

    if dataframe.empty:

        raise ValueError("financial_ratios table is empty.")

    return dataframe


# ============================================================
# SUPPORTING DATA
# ============================================================


def load_supporting_data() -> dict[
    str,
    pd.DataFrame,
]:
    """
    Load all supporting sources required by
    the screener.
    """

    filenames = {
        "companies": "companies.xlsx",
        "sectors": "sectors.xlsx",
        "market_cap": "market_cap.xlsx",
        "profitandloss": "profitandloss.xlsx",
        "balancesheet": "balancesheet.xlsx",
    }

    sources = {}

    for name, filename in filenames.items():

        dataframe = load_excel_source(filename)

        sources[name] = normalize_company_id_column(
            dataframe,
            required=True,
        )

    return sources


# ============================================================
# LATEST ANNUAL RATIO ROWS
# ============================================================


def select_latest_annual_ratios(
    ratios: pd.DataFrame,
) -> pd.DataFrame:
    """
    Select the latest available annual financial-ratio row
    for every company.

    Important rules:
    - Preserve the complete NIFTY 100 company universe.
    - Do NOT require ROE or Debt-to-Equity to be non-null.
    - Do NOT exclude September fiscal years.
    - The latest available financial year is selected independently
      for each company.
    - Missing KPI values remain NaN and are handled by filters later.
    """

    if ratios.empty:
        return ratios.copy()

    df = ratios.copy()

    # ---------------------------------------------------------------
    # Make sure company_id exists
    # ---------------------------------------------------------------

    if "company_id" not in df.columns:
        if "id" in df.columns:
            df = df.rename(columns={"id": "company_id"})
        else:
            raise KeyError("financial_ratios must contain company_id")

    # ---------------------------------------------------------------
    # Extract numeric year.
    #
    # Supports:
    #   2024
    #   "2024"
    #   "2024-03"
    #   "2024-09"
    #   "Mar 2024"
    #   "Sep 2024"
    # ---------------------------------------------------------------

    df["_year_number"] = df["year"].apply(year_number)

    # Keep rows where a year can actually be identified.
    df = df[df["_year_number"].notna()].copy()

    if df.empty:
        return df.drop(columns=["_year_number"], errors="ignore")

    # ---------------------------------------------------------------
    # Sort by company and year.
    #
    # mergesort keeps the original order when two rows have the
    # same numeric year.
    # ---------------------------------------------------------------

    df = df.sort_values(
        ["company_id", "_year_number"],
        ascending=[True, True],
        kind="mergesort",
    )

    # ---------------------------------------------------------------
    # IMPORTANT:
    #
    # Take the latest available row for EACH company.
    #
    # We deliberately do NOT:
    #   - filter out "-09" years
    #   - require ROE
    #   - require Debt-to-Equity
    #
    # Missing metrics will remain NaN.
    # ---------------------------------------------------------------

    latest = (
        df.groupby(
            "company_id",
            as_index=False,
            sort=False,
        )
        .tail(1)
        .copy()
    )

    # ---------------------------------------------------------------
    # Restore original ordering by company_id for predictable output.
    # ---------------------------------------------------------------

    latest = latest.sort_values(
        "company_id",
        kind="mergesort",
    ).reset_index(drop=True)

    # ---------------------------------------------------------------
    # Remove helper column.
    # ---------------------------------------------------------------

    latest = latest.drop(
        columns=["_year_number"],
        errors="ignore",
    )

    return latest


def latest_source_row_per_company(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Select latest annual source row per company.
    """

    result = normalize_company_id_column(
        dataframe,
        required=True,
    ).copy()

    if "year" not in result.columns:

        return result.drop_duplicates(subset=["company_id"]).reset_index(drop=True)

    result["_year_number"] = result["year"].apply(year_number)

    result = result[
        ~result["year"]
        .astype(str)
        .str.contains(
            r"09",
            regex=True,
            na=False,
        )
    ].copy()

    result = result.sort_values(
        [
            "company_id",
            "_year_number",
        ]
    )

    result = (
        result.groupby(
            "company_id",
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    result = result.drop(
        columns=["_year_number"],
        errors="ignore",
    )

    return result.reset_index(drop=True)


# ============================================================
# FCF AVAILABILITY HANDLING
# ============================================================


def attach_latest_available_fcf(
    latest_ratios: pd.DataFrame,
    ratios: pd.DataFrame,
) -> pd.DataFrame:
    """
    Keep the latest ratio row for each company.

    If FCF is missing on that latest ratio row, use the most recent
    historical FCF available for the same company. Never fabricate FCF.
    The source year is recorded in fcf_source_year.
    """
    result = latest_ratios.copy()

    if "free_cash_flow_cr" not in result.columns:
        return result

    history = normalize_company_id_column(
        ratios,
        required=True,
    ).copy()

    if "free_cash_flow_cr" not in history.columns:
        result["fcf_source_year"] = pd.NA
        return result

    history["_year_number"] = history["year"].apply(year_number)
    history["free_cash_flow_cr"] = pd.to_numeric(
        history["free_cash_flow_cr"],
        errors="coerce",
    )

    history = history[
        history["_year_number"].notna() & history["free_cash_flow_cr"].notna()
    ].copy()

    if history.empty:
        result["fcf_source_year"] = pd.NA
        return result

    history = history.sort_values(
        ["company_id", "_year_number"],
        ascending=[True, True],
        kind="mergesort",
    )

    latest_fcf = (
        history.groupby("company_id", as_index=False, sort=False)
        .tail(1)[["company_id", "free_cash_flow_cr", "_year_number"]]
        .rename(
            columns={
                "free_cash_flow_cr": "_latest_available_fcf_cr",
                "_year_number": "_fcf_source_year",
            }
        )
    )

    result = result.merge(
        latest_fcf,
        on="company_id",
        how="left",
    )

    current_fcf = pd.to_numeric(
        result["free_cash_flow_cr"],
        errors="coerce",
    )

    result["free_cash_flow_cr"] = current_fcf.fillna(result["_latest_available_fcf_cr"])

    current_year = result["year"].apply(year_number)

    result["fcf_source_year"] = current_year.where(
        current_fcf.notna(),
        result["_fcf_source_year"],
    )

    return result.drop(
        columns=[
            "_latest_available_fcf_cr",
            "_fcf_source_year",
        ],
        errors="ignore",
    )


# ============================================================
# BUILD SCREENER DATASET
# ============================================================


def build_screener_dataset(
    ratios: pd.DataFrame,
    sources: dict[
        str,
        pd.DataFrame,
    ],
) -> pd.DataFrame:
    """
    Build the latest annual screener dataset.
    """

    ratio_latest = select_latest_annual_ratios(ratios)

    # If the latest ratio row has no FCF, use the most recent
    # historical FCF available for that company.
    ratio_latest = attach_latest_available_fcf(
        ratio_latest,
        ratios,
    )

    # --------------------------------------------------------
    # COMPANIES
    # --------------------------------------------------------

    companies = normalize_company_id_column(
        sources["companies"],
        required=True,
    )

    company_columns = [
        column
        for column in [
            "company_id",
            "company_name",
        ]
        if column in companies.columns
    ]

    company_data = companies[company_columns].drop_duplicates(subset=["company_id"])

    result = ratio_latest.merge(
        company_data,
        on="company_id",
        how="left",
    )

    # --------------------------------------------------------
    # SECTORS
    # --------------------------------------------------------

    sectors = normalize_company_id_column(
        sources["sectors"],
        required=True,
    )

    sector_columns = [
        column
        for column in [
            "company_id",
            "broad_sector",
            "sub_sector",
        ]
        if column in sectors.columns
    ]

    sector_data = sectors[sector_columns].drop_duplicates(subset=["company_id"])

    result = result.merge(
        sector_data,
        on="company_id",
        how="left",
    )

    # --------------------------------------------------------
    # MARKET CAP
    # --------------------------------------------------------

    market_cap = normalize_company_id_column(
        sources["market_cap"],
        required=True,
    )

    market_latest = latest_source_row_per_company(market_cap)

    market_columns = [
        column
        for column in [
            "company_id",
            "market_cap_crore",
            "enterprise_value_crore",
            "pe_ratio",
            "pb_ratio",
            "ev_ebitda",
            "dividend_yield_pct",
        ]
        if column in market_latest.columns
    ]

    if market_columns:

        result = result.merge(
            market_latest[market_columns].drop_duplicates(subset=["company_id"]),
            on="company_id",
            how="left",
        )

    # --------------------------------------------------------
    # P&L
    # --------------------------------------------------------

    profit_loss = normalize_company_id_column(
        sources["profitandloss"],
        required=True,
    )

    pl_latest = latest_source_row_per_company(profit_loss)

    pl_columns = [
        column
        for column in [
            "company_id",
            "sales",
            "net_profit",
            "eps",
            "dividend_payout",
        ]
        if column in pl_latest.columns
    ]

    if pl_columns:

        result = result.merge(
            pl_latest[pl_columns].drop_duplicates(subset=["company_id"]),
            on="company_id",
            how="left",
            suffixes=(
                "",
                "_pl",
            ),
        )

    # --------------------------------------------------------
    # DUPLICATE P&L COLUMNS
    # --------------------------------------------------------

    for column in [
        "sales",
        "net_profit",
        "eps",
        "dividend_payout",
    ]:

        duplicate_column = f"{column}_pl"

        if column not in result.columns and duplicate_column in result.columns:

            result[column] = result[duplicate_column]

        result = result.drop(
            columns=[duplicate_column],
            errors="ignore",
        )

    result = calculate_composite_quality_score(result)

    return result


# ============================================================
# THRESHOLD FILTER
# ============================================================


def apply_threshold(
    series: pd.Series,
    operator_symbol: str,
    threshold: float,
) -> pd.Series:

    if operator_symbol not in OPERATORS:

        raise ValueError(f"Unsupported operator: " f"{operator_symbol}")

    numeric_series = pd.to_numeric(
        series,
        errors="coerce",
    )

    mask = OPERATORS[operator_symbol](
        numeric_series,
        threshold,
    )

    return mask.fillna(False)


# ============================================================
# D/E FILTER
# ============================================================


def apply_de_filter(
    dataframe: pd.DataFrame,
    threshold: float,
) -> pd.Series:
    """
    Financials are exempt from D/E filtering.
    """

    de = pd.to_numeric(
        dataframe["debt_to_equity"],
        errors="coerce",
    )

    sector = dataframe["broad_sector"].fillna("").astype(str).str.strip().str.lower()

    financials = sector.eq("financials")

    return financials | de.le(threshold).fillna(False)


# ============================================================
# EXACT D/E
# ============================================================


def apply_de_exact_filter(
    dataframe: pd.DataFrame,
    target: float,
) -> pd.Series:

    de = pd.to_numeric(
        dataframe["debt_to_equity"],
        errors="coerce",
    )

    sector = dataframe["broad_sector"].fillna("").astype(str).str.strip().str.lower()

    financials = sector.eq("financials")

    return financials | de.eq(target).fillna(False)


# ============================================================
# ICR FILTER
# ============================================================


def apply_icr_filter(
    dataframe: pd.DataFrame,
    threshold: float,
) -> pd.Series:
    """
    Debt Free companies are treated as infinite ICR.
    """

    icr = pd.to_numeric(
        dataframe["interest_coverage"],
        errors="coerce",
    )

    if "icr_label" in dataframe.columns:

        debt_free = (
            dataframe["icr_label"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("debt free")
        )

    else:

        debt_free = pd.Series(
            False,
            index=dataframe.index,
        )

    return debt_free | icr.ge(threshold).fillna(False)


# ============================================================
# FCF POSITIVE
# ============================================================


def apply_fcf_positive_filter(
    dataframe: pd.DataFrame,
) -> pd.Series:

    fcf = pd.to_numeric(
        dataframe["free_cash_flow_cr"],
        errors="coerce",
    )

    return fcf.gt(0).fillna(False)


# ============================================================
# REVENUE CAGR 3Y
# ============================================================


def apply_revenue_cagr_3yr_filter(
    dataframe: pd.DataFrame,
    threshold: float,
) -> pd.Series:

    cagr = pd.to_numeric(
        dataframe["revenue_cagr_3yr"],
        errors="coerce",
    )

    return cagr.ge(threshold).fillna(False)


# ============================================================
# D/E DECLINING YOY
# ============================================================


def calculate_de_declining_flags(
    ratios: pd.DataFrame,
) -> pd.DataFrame:

    dataframe = normalize_company_id_column(
        ratios,
        required=True,
    ).copy()

    dataframe["_year_number"] = dataframe["year"].apply(year_number)

    dataframe["debt_to_equity"] = pd.to_numeric(
        dataframe["debt_to_equity"],
        errors="coerce",
    )

    dataframe = dataframe.sort_values(
        [
            "company_id",
            "_year_number",
        ]
    )

    dataframe["previous_de"] = dataframe.groupby("company_id")["debt_to_equity"].shift(
        1
    )

    dataframe["de_declining_yoy"] = (
        dataframe["debt_to_equity"] < dataframe["previous_de"]
    )

    latest = dataframe.groupby(
        "company_id",
        as_index=False,
    ).tail(1)[
        [
            "company_id",
            "de_declining_yoy",
        ]
    ]

    return latest.reset_index(drop=True)


# ============================================================
# PRESET ENGINE
# ============================================================


def apply_preset(
    dataframe: pd.DataFrame,
    preset_name: str,
    config: dict[str, Any] | None = None,
    original_ratios: pd.DataFrame | None = None,
) -> pd.DataFrame:

    if config is None:
        config = load_config()

    presets = config.get("presets", {})

    if preset_name not in presets:

        raise KeyError(f"Unknown screener preset: " f"{preset_name}")

    preset = presets[preset_name]

    result = dataframe.copy()

    filters = preset.get("filters", {})

    definitions = config.get("filters", {})

    # --------------------------------------------------------
    # STANDARD FILTERS
    # --------------------------------------------------------

    for filter_name, threshold in filters.items():

        if filter_name in {
            "de_exact",
            "fcf_positive_latest",
            "de_declining_yoy",
        }:

            continue

        if filter_name == "revenue_cagr_3yr_min":

            result = result[
                apply_revenue_cagr_3yr_filter(
                    result,
                    float(threshold),
                )
            ].copy()

            continue

        if filter_name not in definitions:

            raise KeyError(
                f"Filter '{filter_name}' " f"is not defined in configuration."
            )

        definition = definitions[filter_name]

        column = definition["column"]

        operator_symbol = definition["operator"]

        if column not in result.columns:

            raise KeyError(
                f"Required screener column "
                f"'{column}' for filter "
                f"'{filter_name}' is missing."
            )

        if filter_name == "de_max":

            mask = apply_de_filter(
                result,
                float(threshold),
            )

        elif filter_name == "icr_min":

            mask = apply_icr_filter(
                result,
                float(threshold),
            )

        else:

            mask = apply_threshold(
                result[column],
                operator_symbol,
                float(threshold),
            )

        result = result[mask].copy()

    # --------------------------------------------------------
    # EXACT D/E
    # --------------------------------------------------------

    if "de_exact" in filters:

        result = result[
            apply_de_exact_filter(
                result,
                float(filters["de_exact"]),
            )
        ].copy()

    # --------------------------------------------------------
    # FCF POSITIVE
    # --------------------------------------------------------

    if filters.get("fcf_positive_latest") is True:

        result = result[apply_fcf_positive_filter(result)].copy()

    # --------------------------------------------------------
    # D/E DECLINING
    # --------------------------------------------------------

    if filters.get("de_declining_yoy") is True:

        if original_ratios is None:

            original_ratios = load_ratio_data()

        flags = calculate_de_declining_flags(original_ratios)

        result = result.merge(
            flags,
            on="company_id",
            how="left",
            suffixes=(
                "",
                "_de",
            ),
        )

        if "de_declining_yoy_de" in result.columns:

            flag_column = "de_declining_yoy_de"

        else:

            flag_column = "de_declining_yoy"

        result = result[result[flag_column].fillna(False)].copy()

        result = result.drop(
            columns=[
                column
                for column in [
                    "de_declining_yoy",
                    "de_declining_yoy_de",
                ]
                if column in result.columns
            ],
            errors="ignore",
        )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    sort_column = preset.get(
        "sort_by",
        "composite_quality_score",
    )

    ascending = bool(
        preset.get(
            "ascending",
            False,
        )
    )

    if sort_column in result.columns:

        result = result.sort_values(
            sort_column,
            ascending=ascending,
            na_position="last",
        )

    return result.reset_index(drop=True)


# ============================================================
# CUSTOM FILTERS
# ============================================================


def apply_custom_filters(
    dataframe: pd.DataFrame,
    filters: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:

    if config is None:
        config = load_config()

    temporary_config = {
        "filters": config.get("filters", {}),
        "presets": {
            "__custom__": {
                "filters": filters,
                "sort_by": "composite_quality_score",
                "ascending": False,
            }
        },
    }

    return apply_preset(
        dataframe,
        "__custom__",
        temporary_config,
    )


# ============================================================
# SUMMARY
# ============================================================


def screener_summary(
    result: pd.DataFrame,
    preset_name: str,
) -> str:

    lines = [
        "=" * 70,
        f"SCREENER: {preset_name}",
        "=" * 70,
        f"Matching companies: " f"{len(result)}",
    ]

    if not result.empty:

        columns = [
            column
            for column in [
                "company_id",
                "company_name",
                "return_on_equity_pct",
                "debt_to_equity",
                "free_cash_flow_cr",
                "revenue_cagr_5yr",
                "pat_cagr_5yr",
                "composite_quality_score",
            ]
            if column in result.columns
        ]

        lines.append("")

        lines.append(result[columns].head(10).to_string(index=False))

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================


def main() -> None:

    print("=" * 70)

    print("NIFTY 100 - SPRINT 3 DAY 15 " "SCREENER ENGINE")

    print("=" * 70)

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    print("\n[1] Loading configuration...")

    config = load_config()

    print(f"[OK] Configuration loaded: " f"{CONFIG_PATH}")

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    print("\n[2] Loading financial ratio data...")

    ratios = load_ratio_data()

    print(f"[OK] financial_ratios rows: " f"{len(ratios):,}")

    # --------------------------------------------------------
    # SOURCES
    # --------------------------------------------------------

    print("\n[3] Loading supporting source data...")

    sources = load_supporting_data()

    for name, dataframe in sources.items():

        print(f"[OK] {name:<15} " f"rows={len(dataframe):,}")

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    print("\n[4] Building screener dataset...")

    dataset = build_screener_dataset(
        ratios,
        sources,
    )

    print(f"[OK] Screener dataset rows: " f"{len(dataset):,}")

    print(f"[OK] Unique companies: " f"{dataset['company_id'].nunique():,}")

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    missing_names = (
        dataset["company_name"].isna().sum()
        if "company_name" in dataset.columns
        else len(dataset)
    )

    missing_sectors = (
        dataset["broad_sector"].isna().sum()
        if "broad_sector" in dataset.columns
        else len(dataset)
    )

    print(f"[CHECK] Missing company names: " f"{missing_names}")

    print(f"[CHECK] Missing sectors: " f"{missing_sectors}")

    # --------------------------------------------------------
    # QUALITY COMPOUNDER
    # --------------------------------------------------------

    print("\n[5] Running Quality Compounder example...")

    quality = apply_preset(
        dataset,
        "Quality Compounder",
        config,
        ratios,
    )

    print(f"[OK] Quality Compounder matches: " f"{len(quality)}")

    if not quality.empty:

        display_columns = [
            column
            for column in [
                "company_id",
                "company_name",
                "return_on_equity_pct",
                "debt_to_equity",
                "free_cash_flow_cr",
                "revenue_cagr_5yr",
                "pat_cagr_5yr",
                "composite_quality_score",
            ]
            if column in quality.columns
        ]

        print()

        print(quality[display_columns].head(10).to_string(index=False))

    # --------------------------------------------------------
    # ALL PRESETS
    # --------------------------------------------------------

    print("\n[6] Running all preset screeners...")

    for preset_name in config.get(
        "presets",
        {},
    ):

        try:

            result = apply_preset(
                dataset,
                preset_name,
                config,
                ratios,
            )

            print(f"[PRESET] " f"{preset_name:<25} " f"{len(result):>3} companies")

        except Exception as error:

            print(f"[ERROR] " f"{preset_name}: " f"{error}")

    print("\n" + "=" * 70)

    print("DAY 15 SCREENER ENGINE COMPLETE")

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
