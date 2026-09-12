from src.analytics.valuation import generate_valuation_files


def main():
    summary, flags, summary_path, flags_path = (
        generate_valuation_files()
    )

    print()
    print("=" * 70)
    print("DAY 26 — VALUATION COMPLETE")
    print("=" * 70)

    print(f"Total companies : {len(summary)}")
    print(f"Flagged rows    : {len(flags)}")

    print()
    print("Flag breakdown:")
    print(summary["flag"].value_counts(dropna=False))

    print()
    print(f"Created: {summary_path}")
    print(f"Created: {flags_path}")

    print("=" * 70)


if __name__ == "__main__":
    main()