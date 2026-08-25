from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")


def inspect_file(file_path):
    print("\n" + "=" * 80)
    print(f"FILE: {file_path.name}")
    print("=" * 80)

    try:
        excel = pd.ExcelFile(file_path)

        print("Sheets:", excel.sheet_names)

        for sheet in excel.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)

            print(f"\n--- Sheet: {sheet} ---")
            print(f"Rows: {len(df)}")
            print(f"Columns: {len(df.columns)}")
            print("Column names:")
            print(list(df.columns))

            print("\nFirst 3 rows:")
            print(df.head(3).to_string(index=False))

    except Exception as error:
        print(f"ERROR: {error}")


def main():
    files = sorted(RAW_DIR.glob("*.xlsx"))

    print(f"Found {len(files)} Excel files.")

    for file_path in files:
        inspect_file(file_path)


if __name__ == "__main__":
    main()