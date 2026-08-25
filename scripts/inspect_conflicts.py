from src.etl.loader import load_all_sources


TABLES = [
    "cashflow",
    "financial_ratios",
    "documents",
]


def inspect_conflicts(table_name, df):
    duplicate_rows = df[
        df.duplicated(
            ["company_id", "year"],
            keep=False,
        )
    ]

    if duplicate_rows.empty:
        return

    for (company_id, year), group in duplicate_rows.groupby(
        ["company_id", "year"]
    ):

        data_columns = [
            column
            for column in group.columns
            if column != "id"
        ]

        # Exact duplicate?
        if group[data_columns].duplicated(
            keep=False
        ).all():
            continue

        print()
        print("=" * 80)
        print(f"TABLE      : {table_name}")
        print(f"COMPANY ID : {company_id}")
        print(f"YEAR       : {year}")
        print("=" * 80)

        print(
            group.to_string(index=False)
        )


def main():

    datasets = load_all_sources()

    print()
    print("=" * 80)
    print("DQ-02 CONFLICTING DUPLICATES")
    print("=" * 80)

    for table_name in TABLES:

        inspect_conflicts(
            table_name,
            datasets[table_name],
        )

    print()
    print("=" * 80)
    print("END OF CONFLICT REPORT")
    print("=" * 80)


if __name__ == "__main__":
    main()