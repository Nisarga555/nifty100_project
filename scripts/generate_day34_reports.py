from pathlib import Path
import sys
import re
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]

OUTPUT = ROOT / "output"
TEARSHEET_DIR = ROOT / "reports" / "tearsheets"
SECTOR_DIR = ROOT / "reports" / "sector"

OUTPUT.mkdir(exist_ok=True)
TEARSHEET_DIR.mkdir(parents=True, exist_ok=True)
SECTOR_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from src.reports.tearsheet import load_data, build_tearsheet


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def safe_filename(value):
    value = clean_text(value)
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def validate_two_pages(path):
    try:
        reader = PdfReader(str(path))
        return len(reader.pages) == 2
    except Exception:
        return False


def get_company_universe(data):
    companies = data["companies"].copy()

    if "id" in companies.columns:
        companies["id"] = (
            companies["id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    return companies


def generate_tearsheets(data, companies):
    print("=" * 70)
    print("SPRINT 5 - DAY 34")
    print("BATCH TEARSHEETS + SECTOR REPORTS")
    print("=" * 70)
    print()

    print(f"Company universe: {len(companies)}")

    generated = 0
    skipped = []
    validation_failures = []

    for index, row in companies.iterrows():

        company_id = clean_text(row["id"]).upper()

        output_path = (
            TEARSHEET_DIR /
            f"{company_id}_tearsheet.pdf"
        )

        try:

            # IMPORTANT:
            # Use the original working tearsheet API.
            result = build_tearsheet(
                company_id,
                data,
            )

            # build_tearsheet may create the PDF itself.
            # If it returns a path, use it; otherwise use
            # the expected output location.

            if isinstance(result, (str, Path)):
                result_path = Path(result)

                if not result_path.is_absolute():
                    result_path = ROOT / result_path

                if result_path.exists():
                    if result_path != output_path:
                        result_path.replace(output_path)

            if not output_path.exists():

                # Some implementations may create the file
                # using their own naming convention.
                candidates = list(
                    TEARSHEET_DIR.glob(
                        f"*{company_id}*.pdf"
                    )
                )

                if candidates:
                    candidates.sort(
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )

                    candidates[0].replace(output_path)

            if not output_path.exists():

                skipped.append(
                    {
                        "company_id": company_id,
                        "reason": "Tearsheet PDF was not created",
                    }
                )

                continue

            if not validate_two_pages(output_path):

                validation_failures.append(
                    {
                        "company_id": company_id,
                        "reason": "PDF does not contain exactly 2 pages",
                    }
                )

                continue

            generated += 1

        except Exception as exc:

            skipped.append(
                {
                    "company_id": company_id,
                    "reason": str(exc),
                }
            )

        if (index + 1) % 10 == 0:
            print(
                f"Processed {index + 1}/{len(companies)}"
            )

    skipped_path = (
        OUTPUT /
        "skipped_tearsheets.csv"
    )

    pd.DataFrame(
        skipped,
        columns=[
            "company_id",
            "reason",
        ],
    ).to_csv(
        skipped_path,
        index=False,
    )

    print()
    print(
        f"Tearsheet generated : {generated}"
    )
    print(
        f"Tearsheet skipped   : {len(skipped)}"
    )
    print()
    print(
        "Tearsheet validation failures: "
        f"{len(validation_failures)}"
    )

    if skipped:
        print()
        print("Skipped companies:")

        for item in skipped:
            print(
                f"  {item['company_id']}: "
                f"{item['reason']}"
            )

    if validation_failures:
        print()
        print("Validation failures:")

        for item in validation_failures:
            print(
                f"  {item['company_id']}: "
                f"{item['reason']}"
            )

    return generated, skipped, validation_failures


def build_sector_report(
    sector_name,
    sector_companies,
    intelligence,
    output_path,
):
    """
    Lightweight sector report using the existing
    cash-flow intelligence output.

    This intentionally avoids changing the existing
    tearsheet architecture.
    """

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    normal_style = styles["Normal"]

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    story = []

    story.append(
        Paragraph(
            f"{sector_name} — Financial Intelligence Report",
            title_style,
        )
    )

    story.append(
        Paragraph(
            f"Companies covered: "
            f"{len(sector_companies)}",
            normal_style,
        )
    )

    story.append(Spacer(1, 10))

    # ----------------------------------------------------------
    # Prepare intelligence data
    # ----------------------------------------------------------

    intel = intelligence.copy()

    if "company_id" in intel.columns:
        intel["company_id"] = (
            intel["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    ids = (
        sector_companies["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
        .tolist()
    )

    sector_intel = intel[
        intel["company_id"].isin(ids)
    ].copy()

    # ----------------------------------------------------------
    # Median summary
    # ----------------------------------------------------------

    story.append(
        Paragraph(
            "Median Cash Flow Intelligence",
            heading_style,
        )
    )

    numeric_cols = [
        (
            "CFO Quality",
            "cfo_quality_score",
        ),
        (
            "CapEx Intensity %",
            "capex_intensity_pct",
        ),
        (
            "FCF CAGR 5Y",
            "fcf_cagr_5yr",
        ),
        (
            "FCF Conversion %",
            "fcf_conversion_pct",
        ),
    ]

    summary = [
        ["Metric", "Median"]
    ]

    for label, column in numeric_cols:

        if column in sector_intel.columns:

            values = pd.to_numeric(
                sector_intel[column],
                errors="coerce",
            ).dropna()

            if len(values):
                value = f"{values.median():.2f}"
            else:
                value = "N/A"

        else:
            value = "N/A"

        summary.append(
            [
                label,
                value,
            ]
        )

    summary_table = Table(
        summary,
        colWidths=[
            75 * mm,
            45 * mm,
        ],
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#D9E2F3"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(summary_table)

    story.append(Spacer(1, 12))

    # ----------------------------------------------------------
    # Company list
    # ----------------------------------------------------------

    story.append(
        Paragraph(
            "Company Comparison",
            heading_style,
        )
    )

    company_table = [
        [
            "Company",
            "CFO Quality",
            "CapEx %",
            "FCF CAGR",
            "Distress",
            "Deleveraging",
            "Capital Allocation",
        ]
    ]

    for _, company in sector_companies.iterrows():

        cid = clean_text(
            company["company_id"]
        ).upper()

        row = sector_intel[
            sector_intel["company_id"] == cid
        ]

        if row.empty:
            company_table.append(
                [
                    clean_text(
                        company.get(
                            "company_name",
                            cid,
                        )
                    ),
                    "N/A",
                    "N/A",
                    "N/A",
                    "N/A",
                    "N/A",
                    "N/A",
                ]
            )
            continue

        r = row.iloc[-1]

        def value(column):
            if column not in r.index:
                return "N/A"

            v = r[column]

            if pd.isna(v):
                return "N/A"

            if isinstance(v, float):
                return f"{v:.2f}"

            return str(v)

        company_table.append(
            [
                clean_text(
                    company.get(
                        "company_name",
                        cid,
                    )
                ),
                value("cfo_quality_score"),
                value("capex_intensity_pct"),
                value("fcf_cagr_5yr"),
                value("distress_flag"),
                value("deleveraging_flag"),
                value("capital_allocation_label"),
            ]
        )

    table = Table(
        company_table,
        colWidths=[
            38 * mm,
            22 * mm,
            20 * mm,
            20 * mm,
            17 * mm,
            20 * mm,
            35 * mm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#D9E2F3"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.grey,
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    6.5,
                ),
                (
                    "LEADING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "WORDWRAP",
                    (0, 0),
                    (-1, -1),
                    "CJK",
                ),
            ]
        )
    )

    story.append(table)

    story.append(Spacer(1, 8))

    story.append(
        Paragraph(
            "N/A indicates unavailable source data. "
            "No financial values are fabricated.",
            styles["Normal"],
        )
    )

    doc.build(story)


def generate_sector_reports(data, companies):
    sectors = data["sectors"].copy()
    intelligence = data["intelligence"].copy()

    sectors["company_id"] = (
        sectors["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    companies["id"] = (
        companies["id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    sector_names = sorted(
        sectors["broad_sector"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    print()
    print(
        f"Sector universe: {len(sector_names)}"
    )

    generated = 0

    for sector_name in sector_names:

        sector_rows = sectors[
            sectors["broad_sector"]
            .astype(str)
            .str.strip()
            .eq(sector_name)
        ].copy()

        company_ids = (
            sector_rows["company_id"]
            .unique()
            .tolist()
        )

        company_rows = companies[
            companies["id"].isin(company_ids)
        ].copy()

        company_rows = company_rows.rename(
            columns={"id": "company_id"}
        )

        output_path = (
            SECTOR_DIR /
            f"{safe_filename(sector_name)}_report.pdf"
        )

        try:

            build_sector_report(
                sector_name,
                company_rows,
                intelligence,
                output_path,
            )

            if output_path.exists():
                generated += 1
                print(
                    f"  {sector_name}: PASS"
                )
            else:
                print(
                    f"  {sector_name}: FAIL"
                )

        except Exception as exc:

            print(
                f"  {sector_name}: FAIL - {exc}"
            )

    return generated


def generate_overall_report(data, companies):
    intelligence = data["intelligence"].copy()

    company_rows = companies.copy()
    company_rows = company_rows.rename(
        columns={"id": "company_id"}
    )

    output_path = (
        SECTOR_DIR /
        "NIFTY_100_Overall_report.pdf"
    )

    build_sector_report(
        "NIFTY 100 Overall",
        company_rows,
        intelligence,
        output_path,
    )

    if output_path.exists():
        print(
            "  NIFTY 100 Overall: PASS"
        )
        return True

    print(
        "  NIFTY 100 Overall: FAIL"
    )

    return False


def main():

    # ----------------------------------------------------------
    # Load the ORIGINAL tearsheet data interface.
    # ----------------------------------------------------------

    data = load_data()

    required_keys = [
        "companies",
        "sectors",
        "pl",
        "bs",
        "cf",
        "pros_cons",
        "intelligence",
    ]

    missing = [
        key for key in required_keys
        if key not in data
    ]

    if missing:
        raise RuntimeError(
            "Missing data keys: "
            + ", ".join(missing)
        )

    companies = get_company_universe(data)

    generated, skipped, validation_failures = (
        generate_tearsheets(
            data,
            companies,
        )
    )

    sector_count = generate_sector_reports(
        data,
        companies,
    )

    print()
    print(
        "Generating NIFTY 100 Overall report..."
    )

    overall_ok = generate_overall_report(
        data,
        companies,
    )

    print()
    print("=" * 70)
    print("DAY 34 VALIDATION")
    print("=" * 70)
    print()

    print(
        f"Companies in universe : {len(companies)}"
    )
    print(
        f"Tearsheets generated  : {generated}"
    )
    print(
        f"Tearsheets skipped    : {len(skipped)}"
    )
    print(
        "Tearsheet validation failures: "
        f"{len(validation_failures)}"
    )
    print(
        f"Source sector reports : {sector_count}"
    )
    print(
        f"Overall report        : "
        f"{'PASS' if overall_ok else 'FAIL'}"
    )
    print(
        f"Total reports         : "
        f"{sector_count + (1 if overall_ok else 0)}"
    )

    failures = []

    if len(companies) != 92:
        failures.append(
            f"Expected 92 companies, found {len(companies)}"
        )

    if generated != 92:
        failures.append(
            f"Expected 92 tearsheets, generated {generated}"
        )

    if skipped:
        failures.append(
            f"{len(skipped)} tearsheets skipped"
        )

    if validation_failures:
        failures.append(
            f"{len(validation_failures)} tearsheet "
            "validation failures"
        )

    if sector_count != 10:
        failures.append(
            f"Expected 10 source sectors, found {sector_count}"
        )

    if not overall_ok:
        failures.append(
            "NIFTY 100 Overall report missing"
        )

    if failures:

        print()

        for failure in failures:
            print(
                f"FAIL: {failure}"
            )

        raise RuntimeError(
            "Day 34 validation failed."
        )

    print()
    print(
        "DAY 34 VALIDATION: PASS"
    )
    print()
    print(
        "92/92 tearsheets generated."
    )
    print(
        "0 tearsheets skipped."
    )
    print(
        "0 tearsheet validation failures."
    )
    print(
        "10 source-supported sector reports generated."
    )
    print(
        "1 NIFTY 100 Overall report generated."
    )
    print(
        "Total reports: 11"
    )
    print()
    print(
        "SPRINT 5 - DAY 34 COMPLETE"
    )


if __name__ == "__main__":
    main()