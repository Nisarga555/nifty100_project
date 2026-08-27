from pathlib import Path
import sqlite3
import math
import pandas as pd

from src.etl.loader import load_all_sources
from src.analytics.ratios import calculate_all_day08_day09_ratios
from src.analytics.cagr import calculate_growth_metrics
from src.analytics.cashflow_kpis import calculate_cashflow_kpis


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "nifty100.sqlite3"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


REQUIRED_KPI_COLUMNS = [
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
    "cash_from_operations_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "composite_quality_score",
]


def clean_key(value):
    if value is None or pd.isna(value):
        return None

    value = str(value).strip().upper()

    if not value or value == "NAN":
        return None

    return value


def clean_year(value):
    if value is None or pd.isna(value):
        return None

    value = str(value).strip().upper()

    if value == "NAN" or value == "":
        return None

    return value


def safe_float(value):
    if value is None or pd.isna(value):
        return None

    try:
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def safe_int_flag(value):
    if value is True:
        return 1

    if value is False:
        return 0

    if value is None or pd.isna(value):
        return None

    try:
        return 1 if bool(value) else 0
    except Exception:
        return None


def get_value(row, column):
    if row is None:
        return None

    return safe_float(row.get(column))


def get_text(row, column):
    if row is None:
        return None

    value = row.get(column)

    if value is None or pd.isna(value):
        return None

    return str(value).strip()


def sign(value):
    value = safe_float(value)

    if value is None:
        return None

    if value > 0:
        return "+"

    if value < 0:
        return "-"

    return "0"


def build_lookup(df):
    lookup = {}

    if df is None or df.empty:
        return lookup

    if "company_id" not in df.columns:
        return lookup

    for _, row in df.iterrows():

        company_id = clean_key(
            row.get("company_id")
        )

        year = clean_year(
            row.get("year")
        )

        if company_id is None or year is None:
            continue

        lookup.setdefault(
            company_id,
            {}
        )

        if year not in lookup[company_id]:
            lookup[company_id][year] = row.to_dict()

    return lookup


def build_company_lookup(df):
    lookup = {}

    if df is None or df.empty:
        return lookup

    for _, row in df.iterrows():

        company_id = clean_key(
            row.get("id")
        )

        if company_id is None:
            continue

        lookup[company_id] = row.to_dict()

    return lookup


def build_sector_lookup(df):
    lookup = {}

    if df is None or df.empty:
        return lookup

    for _, row in df.iterrows():

        company_id = clean_key(
            row.get("company_id")
        )

        if company_id is None:
            continue

        lookup[company_id] = row.to_dict()

    return lookup


def calculate_book_value_per_share(
    balance_row,
    company_row,
):
    if balance_row is None:
        return None

    equity = get_value(
        balance_row,
        "equity_capital"
    )

    reserves = get_value(
        balance_row,
        "reserves"
    )

    if equity is None or reserves is None:
        return None

    face_value = get_value(
        company_row,
        "face_value"
    )

    if face_value is None or face_value <= 0:
        return None

    shares = equity / face_value

    if shares <= 0:
        return None

    return (
        (equity + reserves)
        / shares
    )


def calculate_composite_quality_score(
    row
):
    roe = safe_float(
        row.get(
            "return_on_equity_pct"
        )
    )

    roce = safe_float(
        row.get(
            "return_on_capital_employed_pct"
        )
    )

    fcf = safe_float(
        row.get(
            "free_cash_flow_cr"
        )
    )

    debt_to_equity = safe_float(
        row.get(
            "debt_to_equity"
        )
    )

    components = []

    if roe is not None:
        roe_score = max(
            0.0,
            min(
                100.0,
                roe / 25.0 * 100.0
            )
        )

        components.append(
            (
                roe_score,
                0.30
            )
        )

    if roce is not None:
        roce_score = max(
            0.0,
            min(
                100.0,
                roce / 25.0 * 100.0
            )
        )

        components.append(
            (
                roce_score,
                0.25
            )
        )

    if fcf is not None:
        fcf_score = (
            100.0
            if fcf > 0
            else 0.0
        )

        components.append(
            (
                fcf_score,
                0.25
            )
        )

    if debt_to_equity is not None:
        debt_score = max(
            0.0,
            min(
                100.0,
                (1.0 - debt_to_equity / 5.0)
                * 100.0
            )
        )

        components.append(
            (
                debt_score,
                0.20
            )
        )

    if not components:
        return None

    total_weight = sum(
        weight
        for _, weight in components
    )

    if total_weight <= 0:
        return None

    return (
        sum(
            score * weight
            for score, weight in components
        )
        / total_weight
    )


def classify_capital_allocation(
    cfo,
    cfi,
    cff,
    cfo_quality_score=None,
):
    cfo_sign = sign(cfo)
    cfi_sign = sign(cfi)
    cff_sign = sign(cff)

    pattern = (
        cfo_sign,
        cfi_sign,
        cff_sign,
    )

    if pattern == (
        "+",
        "-",
        "-"
    ):
        quality = safe_float(
            cfo_quality_score
        )

        if (
            quality is not None
            and quality > 1.0
        ):
            return "Shareholder Returns"

        return "Reinvestor"

    if pattern == (
        "+",
        "+",
        "-"
    ):
        return "Liquidating Assets"

    if pattern == (
        "-",
        "+",
        "+"
    ):
        return "Distress Signal"

    if pattern == (
        "-",
        "-",
        "+"
    ):
        return "Growth Funded by Debt"

    if pattern == (
        "+",
        "+",
        "+"
    ):
        return "Cash Accumulator"

    if pattern == (
        "-",
        "-",
        "-"
    ):
        return "Pre-Revenue"

    if pattern == (
        "+",
        "-",
        "+"
    ):
        return "Mixed"

    return "Mixed"


def build_company_year_universe(
    company_lookup,
    profit_lookup,
    balance_lookup,
    cashflow_lookup,
):
    """
    Build the company-year universe from the UNION
    of P&L, Balance Sheet and Cash Flow.

    This is the Day-12 correction that prevents
    the output from being restricted to the P&L-only
    1,070 rows.
    """

    universe = set()

    for company_id in company_lookup:

        p_and_l_years = set(
            profit_lookup.get(
                company_id,
                {}
            ).keys()
        )

        balance_years = set(
            balance_lookup.get(
                company_id,
                {}
            ).keys()
        )

        cashflow_years = set(
            cashflow_lookup.get(
                company_id,
                {}
            ).keys()
        )

        all_years = (
            p_and_l_years
            | balance_years
            | cashflow_years
        )

        for year in all_years:

            if year is not None:
                universe.add(
                    (
                        company_id,
                        year
                    )
                )

    def sort_key(item):

        company_id, year = item

        if year == "TTM":
            year_number = 9999
        else:
            try:
                year_number = int(
                    str(year)[:4]
                )
            except (
                TypeError,
                ValueError
            ):
                year_number = 9998

        return (
            company_id,
            year_number,
            str(year)
        )

    return sorted(
        universe,
        key=sort_key
    )


def prepare_history(
    company_id,
    current_year,
    profit_lookup,
):
    history = []

    company_history = profit_lookup.get(
        company_id,
        {}
    )

    for year, row in company_history.items():

        if year == current_year:
            continue

        history.append(
            {
                "year": year,
                "sales": row.get(
                    "sales"
                ),
                "net_profit": row.get(
                    "net_profit"
                ),
                "eps": row.get(
                    "eps"
                ),
            }
        )

    return history


def calculate_growth_safely(
    history
):
    if not history:
        return {}

    try:
        result = calculate_growth_metrics(
            history
        )

        if result is None:
            return {}

        return result

    except TypeError:

        try:
            result = calculate_growth_metrics(
                pd.DataFrame(history)
            )

            if result is None:
                return {}

            return result

        except Exception:
            return {}

    except Exception:
        return {}


def normalize_growth_columns(
    row
):
    aliases = {
        "revenue_cagr_3yr": [
            "revenue_cagr_3yr",
            "sales_cagr_3yr",
        ],
        "revenue_cagr_3yr_flag": [
            "revenue_cagr_3yr_flag",
            "sales_cagr_3yr_flag",
        ],
        "revenue_cagr_5yr": [
            "revenue_cagr_5yr",
            "sales_cagr_5yr",
        ],
        "revenue_cagr_5yr_flag": [
            "revenue_cagr_5yr_flag",
            "sales_cagr_5yr_flag",
        ],
        "revenue_cagr_10yr": [
            "revenue_cagr_10yr",
            "sales_cagr_10yr",
        ],
        "revenue_cagr_10yr_flag": [
            "revenue_cagr_10yr_flag",
            "sales_cagr_10yr_flag",
        ],
        "pat_cagr_3yr": [
            "pat_cagr_3yr",
            "net_profit_cagr_3yr",
        ],
        "pat_cagr_3yr_flag": [
            "pat_cagr_3yr_flag",
            "net_profit_cagr_3yr_flag",
        ],
        "pat_cagr_5yr": [
            "pat_cagr_5yr",
            "net_profit_cagr_5yr",
        ],
        "pat_cagr_5yr_flag": [
            "pat_cagr_5yr_flag",
            "net_profit_cagr_5yr_flag",
        ],
        "pat_cagr_10yr": [
            "pat_cagr_10yr",
            "net_profit_cagr_10yr",
        ],
        "pat_cagr_10yr_flag": [
            "pat_cagr_10yr_flag",
            "net_profit_cagr_10yr_flag",
        ],
        "eps_cagr_3yr": [
            "eps_cagr_3yr",
        ],
        "eps_cagr_3yr_flag": [
            "eps_cagr_3yr_flag",
        ],
        "eps_cagr_5yr": [
            "eps_cagr_5yr",
        ],
        "eps_cagr_5yr_flag": [
            "eps_cagr_5yr_flag",
        ],
        "eps_cagr_10yr": [
            "eps_cagr_10yr",
        ],
        "eps_cagr_10yr_flag": [
            "eps_cagr_10yr_flag",
        ],
    }

    for target, possible_names in aliases.items():

        if target in row:
            continue

        row[target] = None

        for name in possible_names:

            if name in row:

                row[target] = row[name]
                break


def calculate_cashflow_values(
    cashflow_row,
    profit_row,
):
    result = {}

    if cashflow_row is None:
        result["free_cash_flow_cr"] = None
        result["capex_cr"] = None
        result["cash_from_operations_cr"] = None

        return result

    cfo = get_value(
        cashflow_row,
        "operating_activity"
    )

    cfi = get_value(
        cashflow_row,
        "investing_activity"
    )

    result["cash_from_operations_cr"] = cfo

    if cfo is not None and cfi is not None:
        result["free_cash_flow_cr"] = (
            cfo + cfi
        )
    else:
        result["free_cash_flow_cr"] = None

    if cfi is not None:
        result["capex_cr"] = abs(cfi)
    else:
        result["capex_cr"] = None

    # Use the project's existing cash-flow KPI
    # implementation where possible.
    try:
        source = {}

        if profit_row:
            source.update(profit_row)

        source.update(cashflow_row)

        cashflow_result = calculate_cashflow_kpis(
            source
        )

        if isinstance(
            cashflow_result,
            dict
        ):
            result.update(
                cashflow_result
            )

    except Exception:
        pass

    return result


def calculate_one_company_year(
    company_id,
    year,
    company_row,
    profit_row,
    balance_row,
    cashflow_row,
    sector_row,
    history,
):
    source = {}

    if company_row:
        source.update(
            company_row
        )

    if profit_row:
        source.update(
            profit_row
        )

    if balance_row:
        source.update(
            balance_row
        )

    if cashflow_row:
        source.update(
            cashflow_row
        )

    if sector_row:
        source.update(
            sector_row
        )

    result = {
        "company_id": company_id,
        "year": year,
    }

    # ------------------------------------------------------------
    # Day 08 + Day 09 ratio engine
    # ------------------------------------------------------------

    try:

        ratio_result = (
            calculate_all_day08_day09_ratios(
                source
            )
        )

        if isinstance(
            ratio_result,
            dict
        ):
            result.update(
                ratio_result
            )

    except Exception as exc:

        print(
            f"[WARNING] Ratio calculation failed "
            f"for {company_id} {year}: {exc}"
        )

    # ------------------------------------------------------------
    # Source KPI values
    # ------------------------------------------------------------

    result["earnings_per_share"] = (
        get_value(
            profit_row,
            "eps"
        )
    )

    result["dividend_payout_ratio_pct"] = (
        get_value(
            profit_row,
            "dividend_payout"
        )
    )

    result["total_debt_cr"] = (
        get_value(
            balance_row,
            "borrowings"
        )
    )

    result["book_value_per_share"] = (
        calculate_book_value_per_share(
            balance_row,
            company_row
        )
    )

    # ------------------------------------------------------------
    # Cash-flow KPIs
    # ------------------------------------------------------------

    cashflow_values = (
        calculate_cashflow_values(
            cashflow_row,
            profit_row,
        )
    )

    result.update(
        cashflow_values
    )

    # ------------------------------------------------------------
    # Growth / CAGR engine
    # ------------------------------------------------------------

    growth_history = list(
        history
    )

    if profit_row is not None:

        growth_history.append(
            {
                "year": year,
                "sales": get_value(
                    profit_row,
                    "sales"
                ),
                "net_profit": get_value(
                    profit_row,
                    "net_profit"
                ),
                "eps": get_value(
                    profit_row,
                    "eps"
                ),
            }
        )

    growth_result = calculate_growth_safely(
        growth_history
    )

    if growth_result:
        result.update(
            growth_result
        )

    normalize_growth_columns(
        result
    )

    # ------------------------------------------------------------
    # Composite quality score
    # ------------------------------------------------------------

    result[
        "composite_quality_score"
    ] = calculate_composite_quality_score(
        result
    )

    return result


def create_database_schema(
    connection
):
    cursor = connection.cursor()

    cursor.execute(
        """
        DROP TABLE IF EXISTS financial_ratios
        """
    )

    cursor.execute(
        """
        CREATE TABLE financial_ratios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            company_id TEXT NOT NULL,
            year TEXT NOT NULL,

            net_profit_margin_pct REAL,
            operating_profit_margin_pct REAL,
            return_on_equity_pct REAL,
            return_on_capital_employed_pct REAL,
            return_on_assets_pct REAL,

            debt_to_equity REAL,
            high_leverage_flag INTEGER,

            interest_coverage REAL,
            icr_label TEXT,
            icr_warning_flag INTEGER,

            net_debt_cr REAL,
            asset_turnover REAL,

            free_cash_flow_cr REAL,

            cfo_quality_score REAL,
            cfo_quality_label TEXT,

            capex_cr REAL,
            capex_intensity_pct REAL,
            capex_intensity_label TEXT,

            fcf_conversion_rate_pct REAL,

            earnings_per_share REAL,
            book_value_per_share REAL,
            dividend_payout_ratio_pct REAL,

            total_debt_cr REAL,
            cash_from_operations_cr REAL,

            revenue_cagr_3yr REAL,
            revenue_cagr_3yr_flag TEXT,
            revenue_cagr_5yr REAL,
            revenue_cagr_5yr_flag TEXT,
            revenue_cagr_10yr REAL,
            revenue_cagr_10yr_flag TEXT,

            pat_cagr_3yr REAL,
            pat_cagr_3yr_flag TEXT,
            pat_cagr_5yr REAL,
            pat_cagr_5yr_flag TEXT,
            pat_cagr_10yr REAL,
            pat_cagr_10yr_flag TEXT,

            eps_cagr_3yr REAL,
            eps_cagr_3yr_flag TEXT,
            eps_cagr_5yr REAL,
            eps_cagr_5yr_flag TEXT,
            eps_cagr_10yr REAL,
            eps_cagr_10yr_flag TEXT,

            composite_quality_score REAL,

            UNIQUE(company_id, year)
        )
        """
    )

    connection.commit()


def prepare_dataframe(
    records
):
    df = pd.DataFrame(
        records
    )

    if df.empty:
        return df

    # Remove private helper columns.
    private_columns = [
        column
        for column in df.columns
        if column.startswith("_")
    ]

    if private_columns:
        df = df.drop(
            columns=private_columns
        )

    # Guarantee required columns.
    for column in REQUIRED_KPI_COLUMNS:

        if column not in df.columns:
            df[column] = None

    # Convert boolean flags to SQLite-safe integers.
    for column in [
        "high_leverage_flag",
        "icr_warning_flag",
    ]:

        if column in df.columns:
            df[column] = (
                df[column]
                .apply(
                    safe_int_flag
                )
            )

    # Normalize company/year.
    df["company_id"] = (
        df["company_id"]
        .apply(clean_key)
    )

    df["year"] = (
        df["year"]
        .apply(clean_year)
    )

    # Drop invalid keys.
    df = df[
        df["company_id"].notna()
        & df["year"].notna()
    ]

    # Defensively remove duplicate company-years.
    df = (
        df.drop_duplicates(
            subset=[
                "company_id",
                "year",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return df


def write_capital_allocation(
    records
):
    output = []

    for record in records:

        cfo = record.get(
            "_cfo"
        )

        cfi = record.get(
            "_cfi"
        )

        cff = record.get(
            "_cff"
        )

        quality = record.get(
            "cfo_quality_score"
        )

        output.append(
            {
                "company_id":
                    record.get(
                        "company_id"
                    ),

                "year":
                    record.get(
                        "year"
                    ),

                "cfo_sign":
                    sign(cfo),

                "cfi_sign":
                    sign(cfi),

                "cff_sign":
                    sign(cff),

                "pattern_label":
                    classify_capital_allocation(
                        cfo,
                        cfi,
                        cff,
                        quality,
                    ),
            }
        )

    capital_df = pd.DataFrame(
        output,
        columns=[
            "company_id",
            "year",
            "cfo_sign",
            "cfi_sign",
            "cff_sign",
            "pattern_label",
        ],
    )

    path = (
        OUTPUT_DIR
        / "capital_allocation.csv"
    )

    capital_df.to_csv(
        path,
        index=False
    )

    return capital_df, path


def main():

    print("=" * 70)
    print(
        "NIFTY 100 - DAY 12 FINANCIAL RATIO ENGINE"
    )
    print("=" * 70)

    # ------------------------------------------------------------
    # Load cleaned ETL sources
    # ------------------------------------------------------------

    datasets = load_all_sources()

    companies = datasets.get(
        "companies",
        pd.DataFrame()
    )

    profitandloss = datasets.get(
        "profitandloss",
        pd.DataFrame()
    )

    balancesheet = datasets.get(
        "balancesheet",
        pd.DataFrame()
    )

    cashflow = datasets.get(
        "cashflow",
        pd.DataFrame()
    )

    sectors = datasets.get(
        "sectors",
        pd.DataFrame()
    )

    # ------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------

    company_lookup = (
        build_company_lookup(
            companies
        )
    )

    profit_lookup = (
        build_lookup(
            profitandloss
        )
    )

    balance_lookup = (
        build_lookup(
            balancesheet
        )
    )

    cashflow_lookup = (
        build_lookup(
            cashflow
        )
    )

    sector_lookup = (
        build_sector_lookup(
            sectors
        )
    )

    # ------------------------------------------------------------
    # IMPORTANT:
    # UNION P&L + Balance Sheet + Cash Flow
    # ------------------------------------------------------------

    universe = (
        build_company_year_universe(
            company_lookup,
            profit_lookup,
            balance_lookup,
            cashflow_lookup,
        )
    )

    records = []

    for company_id, year in universe:

        company_row = (
            company_lookup.get(
                company_id
            )
        )

        profit_row = (
            profit_lookup
            .get(
                company_id,
                {}
            )
            .get(
                year
            )
        )

        balance_row = (
            balance_lookup
            .get(
                company_id,
                {}
            )
            .get(
                year
            )
        )

        cashflow_row = (
            cashflow_lookup
            .get(
                company_id,
                {}
            )
            .get(
                year
            )
        )

        sector_row = (
            sector_lookup.get(
                company_id
            )
        )

        history = (
            prepare_history(
                company_id,
                year,
                profit_lookup,
            )
        )

        result = (
            calculate_one_company_year(
                company_id=company_id,
                year=year,
                company_row=company_row,
                profit_row=profit_row,
                balance_row=balance_row,
                cashflow_row=cashflow_row,
                sector_row=sector_row,
                history=history,
            )
        )

        # Private fields used only by capital allocation CSV.
        result["_cfo"] = (
            get_value(
                cashflow_row,
                "operating_activity"
            )
        )

        result["_cfi"] = (
            get_value(
                cashflow_row,
                "investing_activity"
            )
        )

        result["_cff"] = (
            get_value(
                cashflow_row,
                "financing_activity"
            )
        )

        records.append(
            result
        )

    print()
    print(
        "Calculated company-year rows:",
        len(records)
    )

    # ------------------------------------------------------------
    # Prepare database DataFrame
    # ------------------------------------------------------------

    df = prepare_dataframe(
        records
    )

    # ------------------------------------------------------------
    # Create DB
    # ------------------------------------------------------------

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    try:

        create_database_schema(
            connection
        )

        # --------------------------------------------------------
        # Synchronize SQLite schema with calculated KPI columns.
        #
        # The ratio engine may expose diagnostic/source columns
        # such as reported_opm_percentage. Add any such columns
        # automatically instead of failing during INSERT.
        # --------------------------------------------------------

        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(financial_ratios)"
            ).fetchall()
        }

        for column in df.columns:

            if column in existing_columns:
                continue

            series = df[column]

            if (
                pd.api.types.is_numeric_dtype(series)
                and not pd.api.types.is_bool_dtype(series)
            ):
                sqlite_type = "REAL"
            else:
                sqlite_type = "TEXT"

            safe_column = (
                str(column)
                .replace('"', '""')
            )

            connection.execute(
                f'ALTER TABLE financial_ratios '
                f'ADD COLUMN "{safe_column}" {sqlite_type}'
            )

        connection.commit()

        df.to_sql(
            "financial_ratios",
            connection,
            if_exists="append",
            index=False,
        )

        connection.commit()

        database_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM financial_ratios
                """
            )
            .fetchone()[0]
        )

    finally:

        connection.close()

    print(
        "financial_ratios rows:",
        database_count
    )

    # ------------------------------------------------------------
    # Capital allocation CSV
    # ------------------------------------------------------------

    capital_df, capital_path = (
        write_capital_allocation(
            records
        )
    )

    print(
        "Capital allocation rows:",
        len(capital_df)
    )

    print(
        "Capital allocation report:",
        capital_path
    )

    # ------------------------------------------------------------
    # Final Day-12 status
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "DAY 12 POPULATION COMPLETE"
    )
    print("=" * 70)

    if database_count >= 1100:

        print(
            "[PASS] financial_ratios has "
            f"{database_count} rows; "
            "target is >= 1,100"
        )

    else:

        print(
            "[WARNING] financial_ratios has "
            f"{database_count} rows; "
            "target is >= 1,100"
        )

    # Check required columns.
    missing_columns = [
        column
        for column in REQUIRED_KPI_COLUMNS
        if column not in df.columns
    ]

    if not missing_columns:

        print(
            "[OK] All required KPI columns exist"
        )

    else:

        print(
            "[WARNING] Missing KPI columns:",
            ", ".join(
                missing_columns
            )
        )

    print(
        "[OK] SQLite database created"
    )

    print(
        "[OK] Capital allocation CSV created"
    )


if __name__ == "__main__":
    main()