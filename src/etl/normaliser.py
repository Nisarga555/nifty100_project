import re
from datetime import datetime

import pandas as pd


# =====================================================================
# TICKER ALIASES
# =====================================================================
# Source files sometimes contain ticker spelling mistakes/aliases.
# These are normalized to the canonical ticker used by companies.id.

TICKER_ALIASES = {
    "AGTL": "ATGL",
}


# =====================================================================
# YEAR NORMALIZATION
# =====================================================================

def normalize_year(value):
    """
    Normalize reporting periods while preserving the month.

    Examples:
        2024       -> 2024
        "2024"     -> 2024
        "Mar 2024" -> "2024-03"
        "Sep 2024" -> "2024-09"
        "Dec 2012" -> "2012-12"
        "Jun 2020" -> "2020-06"
        "Mar-13"   -> "2013-03"
    """

    if pd.isna(value):
        return None

    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m")

    value = str(value).strip()

    # Four-digit year only
    if re.fullmatch(r"(19|20)\d{2}", value):
        return int(value)

    # Handle values that may look like 2024.0
    if re.fullmatch(r"(19|20)\d{2}\.0", value):
        return int(float(value))

    # Month + four-digit year
    match = re.fullmatch(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*[\s-]+(\d{4})",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        month = match.group(1).title()
        year = int(match.group(2))

        month_number = datetime.strptime(
            month,
            "%b",
        ).month

        return f"{year:04d}-{month_number:02d}"

    # Month + two-digit year
    match = re.fullmatch(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*[\s-]+(\d{2})",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        month = match.group(1).title()
        short_year = int(match.group(2))

        year = (
            1900 + short_year
            if short_year >= 50
            else 2000 + short_year
        )

        month_number = datetime.strptime(
            month,
            "%b",
        ).month

        return f"{year:04d}-{month_number:02d}"

    return None


# =====================================================================
# TICKER NORMALIZATION
# =====================================================================

def normalize_ticker(value):
    """
    Standardize company ticker/company ID.

    Examples:
        "abb"       -> "ABB"
        " ABB "     -> "ABB"
        "AdaniPort" -> "ADANIPORT"

    Source aliases are also converted to their canonical ticker.

    Example:
        "AGTL" -> "ATGL"
    """

    if pd.isna(value):
        return None

    value = str(value).strip().upper()

    # Remove unnecessary spaces
    value = re.sub(r"\s+", "", value)

    # Convert known source aliases to canonical ticker
    value = TICKER_ALIASES.get(
        value,
        value,
    )

    return value


# =====================================================================
# NUMERIC NORMALIZATION
# =====================================================================

def normalize_numeric(value):
    """
    Convert common Excel/string numeric formats into float.

    Examples:
        1,234   -> 1234.0
        12.5    -> 12.5
        25%     -> 25.0
        (500)   -> -500.0
        -       -> None
    """

    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    if value in {
        "",
        "-",
        "—",
        "NA",
        "N/A",
        "nan",
        "None",
    }:
        return None

    # Negative numbers written as (500)
    negative = (
        value.startswith("(")
        and value.endswith(")")
    )

    # Remove formatting
    value = value.replace(",", "")
    value = value.replace("%", "")
    value = value.replace("₹", "")
    value = value.replace("Rs.", "")
    value = value.replace("Rs", "")

    value = value.strip("() ")

    try:
        number = float(value)

        if negative:
            number = -number

        return number

    except ValueError:
        return None


# =====================================================================
# DATE NORMALIZATION
# =====================================================================

def normalize_date(value):
    """
    Convert a date value into YYYY-MM-DD.
    """

    if pd.isna(value):
        return None

    try:
        date_value = pd.to_datetime(value)

        return date_value.strftime("%Y-%m-%d")

    except (ValueError, TypeError):
        return None


# =====================================================================
# BOOLEAN NORMALIZATION
# =====================================================================

def normalize_boolean(value):
    """
    Convert common boolean representations to True/False.
    """

    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    value = str(value).strip().lower()

    if value in {
        "true",
        "yes",
        "y",
        "1",
    }:
        return True

    if value in {
        "false",
        "no",
        "n",
        "0",
    }:
        return False

    return None


# =====================================================================
# COLUMN NAME CLEANING
# =====================================================================

def clean_column_name(column):
    """
    Convert column names into consistent snake_case.

    Example:
        Operating Profit Margin %
        ->
        operating_profit_margin
    """

    column = str(column).strip().lower()

    column = re.sub(
        r"[^a-z0-9]+",
        "_",
        column,
    )

    return column.strip("_")


# =====================================================================
# EXCEL HEADER PROMOTION
# =====================================================================

def promote_excel_header(df):
    """
    Some source Excel files contain a title row
    before the actual column headers.

    Detect that structure and promote the correct row.
    """

    if df.empty:
        return df

    first_column = str(df.columns[0]).lower()

    if (
        "bluestock" in first_column
        or "nifty 100" in first_column
    ):
        df = df.copy()

        df.columns = df.iloc[0]

        df = df.iloc[1:].reset_index(drop=True)

    return df


# =====================================================================
# DATAFRAME NORMALIZATION
# =====================================================================

def normalize_dataframe(df):
    """
    Apply dataframe-level normalization.

    This function:
        1. Fixes title/header rows
        2. Cleans column names
        3. Normalizes company IDs
        4. Normalizes reporting periods
        5. Normalizes dates
    """

    df = promote_excel_header(df)

    # ---------------------------------------------------------------
    # Clean column names
    # ---------------------------------------------------------------

    df.columns = [
        clean_column_name(column)
        for column in df.columns
    ]

    # ---------------------------------------------------------------
    # Normalize company IDs
    # ---------------------------------------------------------------

    if "company_id" in df.columns:

        df["company_id"] = df[
            "company_id"
        ].apply(
            normalize_ticker
        )

    # ---------------------------------------------------------------
    # Normalize reporting period
    # ---------------------------------------------------------------

    if "year" in df.columns:

        df["year"] = df[
            "year"
        ].apply(
            normalize_year
        )

    # ---------------------------------------------------------------
    # Normalize dates
    # ---------------------------------------------------------------

    if "date" in df.columns:

        df["date"] = df[
            "date"
        ].apply(
            normalize_date
        )

    return df