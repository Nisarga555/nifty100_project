from src.etl.loader import load_all_sources


TABLES = [
    "profitandloss",
    "balancesheet",
    "cashflow",
    "financial_ratios",
    "documents",
]


def analyze_table(table_name, df):
    duplicate_rows = df[
        df.duplicated(
            ["company_id", "year"],
            keep=False,
        )
    ]

    if duplicate_rows.empty:
        print(f"{table_name}: no duplicates")
        return

    exact_groups = 0
    conflicting_groups = 0

    for _, group in duplicate_rows.groupby(
        ["company_id", "year"]
    ):

        # Ignore id because duplicate records
        # naturally have different row IDs.
        data_columns = [
            col for col in group.columns
            if col != "id"
        ]

        if group[data_columns].duplicated(
            keep=False
        ).all():

            exact_groups += 1

        else:
            conflicting_groups += 1

    print(
        f"{table_name}: "
        f"exact duplicate groups={exact_groups}, "
        f"conflicting groups={conflicting_groups}"
    )


def main():

    datasets = load_all_sources()

    print("=" * 70)
    print("DUPLICATE GROUP ANALYSIS")
    print("=" * 70)

    for table_name in TABLES:

        analyze_table(
            table_name,
            datasets[table_name],
        )


if __name__ == "__main__":
    main()