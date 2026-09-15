from pathlib import Path
import re
import pandas as pd


INPUT_FILE = Path("data/raw/analysis.xlsx")
PARSED_OUTPUT = Path("output/analysis_parsed.csv")
FAILURE_OUTPUT = Path("output/parse_failures.csv")


TARGET_FIELDS = [
    "compounded_sales_growth",
    "compounded_profit_growth",
    "stock_price_cagr",
    "roe",
]


# Matches:
# 10 Years: 21%
# 5 Years: 24%
# 3 Years: -1%
#
# Allows arbitrary spaces around "Years", colon and value.
YEAR_PATTERN = re.compile(
    r"(\d+)\s*Years?:?\s*([-+]?\d+(?:\.\d+)?)%"
)


def parse_year_percentage(value):
    """
    Parse values such as:
        '10 Years: 21%' -> (10, 21.0)
        '5 Years: -3%'  -> (5, -3.0)

    Returns:
        (period_years, value_pct)
        or (None, None) if the value cannot be parsed.
    """

    if pd.isna(value):
        return None, None

    text = str(value).strip()

    match = YEAR_PATTERN.search(text)

    if not match:
        return None, None

    period_years = int(match.group(1))
    value_pct = float(match.group(2))

    return period_years, value_pct


def parse_analysis():
    """
    Read analysis.xlsx, parse the four target fields,
    and generate analysis_parsed.csv and parse_failures.csv.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    # Row 0 is the title row, so actual headers are row 1.
    df = pd.read_excel(INPUT_FILE, header=1)

    required_columns = ["company_id"] + TARGET_FIELDS

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    parsed_rows = []
    failures = []

    for _, row in df.iterrows():

        company_id = str(row["company_id"]).strip()

        for metric_type in TARGET_FIELDS:

            raw_value = row[metric_type]

            period_years, value_pct = parse_year_percentage(raw_value)

            if period_years is not None:
                parsed_rows.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "period_years": period_years,
                        "value_pct": value_pct,
                    }
                )
            else:
                failures.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "raw_value": raw_value,
                    }
                )

    parsed_df = pd.DataFrame(
        parsed_rows,
        columns=[
            "company_id",
            "metric_type",
            "period_years",
            "value_pct",
        ],
    )

    failures_df = pd.DataFrame(
        failures,
        columns=[
            "company_id",
            "metric_type",
            "raw_value",
        ],
    )

    PARSED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    parsed_df.to_csv(PARSED_OUTPUT, index=False)
    failures_df.to_csv(FAILURE_OUTPUT, index=False)

    print("=" * 60)
    print("ANALYSIS PARSER COMPLETE")
    print("=" * 60)
    print(f"Input rows       : {len(df)}")
    print(f"Parsed rows      : {len(parsed_df)}")
    print(f"Parse failures   : {len(failures_df)}")
    print(f"Parsed output    : {PARSED_OUTPUT}")
    print(f"Failure output   : {FAILURE_OUTPUT}")
    print()

    if not parsed_df.empty:
        print("Parsed by metric:")
        print(parsed_df["metric_type"].value_counts().to_string())
        print()

        print("Parsed by period:")
        print(parsed_df["period_years"].value_counts().sort_index().to_string())

    if not failures_df.empty:
        print()
        print("Failure examples:")
        print(failures_df.head(10).to_string(index=False))


if __name__ == "__main__":
    parse_analysis()