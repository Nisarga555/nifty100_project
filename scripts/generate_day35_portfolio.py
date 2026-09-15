from pathlib import Path
import sys
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
REPORT_DIR = ROOT / "reports" / "portfolio"

OUTPUT.mkdir(exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from src.reports.tearsheet import load_data


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def num(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def trend_arrow(current, previous):
    current = num(current)
    previous = num(previous)

    if current is None or previous is None:
        return "→"

    if previous == 0:
        if current > 0:
            return "↑"
        if current < 0:
            return "↓"
        return "→"

    change = abs((current - previous) / abs(previous))

    if change <= 0.02:
        return "→"

    return "↑" if current > previous else "↓"


def make_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="PortfolioTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=23,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CompanyTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=21,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
        )
    )

    styles.add(
        ParagraphStyle(
            name="KPI",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
        )
    )

    return styles


def generate_portfolio_report(data):

    companies = data["companies"].copy()
    intelligence = data["intelligence"].copy()

    companies["id"] = (
        companies["id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    intelligence["company_id"] = (
        intelligence["company_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    companies = companies.sort_values("id")

    output_path = (
        REPORT_DIR /
        "portfolio_summary.pdf"
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = make_styles()
    story = []

    # ==========================================================
    # COVER / RETROSPECTIVE
    # ==========================================================

    story.append(
        Paragraph(
            "NIFTY 100 Portfolio Summary",
            styles["PortfolioTitle"],
        )
    )

    story.append(
        Paragraph(
            "Sprint 5 — Portfolio Intelligence Report",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            f"Companies covered: {len(companies)}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "<b>Retrospective</b>",
            styles["Heading2"],
        )
    )

    retrospective = [
        ["Area", "Sprint 5 Output"],
        [
            "NLP",
            "Automated pros and cons with confidence scores",
        ],
        [
            "Cash Flow",
            "CFO quality, CapEx intensity and FCF intelligence",
        ],
        [
            "Capital Allocation",
            "8-pattern classification and YoY changes",
        ],
        [
            "Company Reports",
            "92 two-page company tearsheets",
        ],
        [
            "Sector Reports",
            "10 source-supported sectors + overall report",
        ],
        [
            "Portfolio",
            "Alphabetical one-page company summary",
        ],
    ]

    table = Table(
        retrospective,
        colWidths=[
            48 * mm,
            125 * mm,
        ],
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
                    0.4,
                    colors.grey,
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "LEADING",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(table)

    story.append(PageBreak())

    # ==========================================================
    # ONE PAGE PER COMPANY
    # ==========================================================

    for _, company in companies.iterrows():

        cid = clean(company["id"])

        name = clean(
            company.get(
                "company_name",
                cid,
            )
        )

        row = intelligence[
            intelligence["company_id"] == cid
        ]

        if row.empty:
            latest = pd.Series(dtype=object)
        else:
            latest = row.iloc[-1]

        story.append(
            Paragraph(
                f"{name} ({cid})",
                styles["CompanyTitle"],
            )
        )

        # ------------------------------------------------------
        # SIX KPIs
        # ------------------------------------------------------

        kpis = [
            (
                "ROE",
                "return_on_equity_pct",
                "%",
            ),
            (
                "ROCE",
                "return_on_capital_employed_pct",
                "%",
            ),
            (
                "NPM",
                "net_profit_margin_pct",
                "%",
            ),
            (
                "D/E",
                "debt_to_equity",
                "",
            ),
            (
                "FCF",
                "free_cash_flow_cr",
                " Cr",
            ),
            (
                "CFO Quality",
                "cfo_quality_score",
                "",
            ),
        ]

        kpi_data = []

        for i in range(0, 6, 2):

            row_data = []

            for label, column, suffix in kpis[i:i + 2]:

                value = (
                    num(latest.get(column))
                    if not latest.empty
                    else None
                )

                if value is None:
                    display = "N/A"
                else:
                    display = f"{value:.2f}{suffix}"

                row_data.append(
                    Paragraph(
                        f"<b>{label}</b><br/>"
                        f"{display} →",
                        styles["KPI"],
                    )
                )

            kpi_data.append(row_data)

        kpi_table = Table(
            kpi_data,
            colWidths=[
                80 * mm,
                80 * mm,
            ],
            rowHeights=[
                16 * mm,
                16 * mm,
                16 * mm,
            ],
        )

        kpi_table.setStyle(
            TableStyle(
                [
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.6,
                        colors.HexColor("#777777"),
                    ),
                    (
                        "INNERGRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.HexColor("#BBBBBB"),
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
                        7,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                ]
            )
        )

        story.append(kpi_table)

        story.append(Spacer(1, 10))

        # ------------------------------------------------------
        # CASH FLOW INTELLIGENCE
        # ------------------------------------------------------

        story.append(
            Paragraph(
                "<b>Cash Flow & Capital Allocation Intelligence</b>",
                styles["Heading2"],
            )
        )

        intelligence_rows = [
            ["Metric", "Value"],
        ]

        fields = [
            (
                "CFO Quality Score",
                "cfo_quality_score",
            ),
            (
                "CFO Quality Label",
                "cfo_quality_label",
            ),
            (
                "CapEx Intensity %",
                "capex_intensity_pct",
            ),
            (
                "CapEx Label",
                "capex_label",
            ),
            (
                "FCF CAGR 5Y %",
                "fcf_cagr_5yr",
            ),
            (
                "FCF Conversion %",
                "fcf_conversion_pct",
            ),
            (
                "Distress Flag",
                "distress_flag",
            ),
            (
                "Deleveraging Flag",
                "deleveraging_flag",
            ),
            (
                "Capital Allocation",
                "capital_allocation_label",
            ),
        ]

        for label, column in fields:

            if latest.empty or column not in latest.index:
                value = "N/A"
            else:
                raw = latest[column]

                if pd.isna(raw):
                    value = "N/A"
                elif isinstance(raw, float):
                    value = f"{raw:.2f}"
                else:
                    value = str(raw)

            intelligence_rows.append(
                [
                    label,
                    value,
                ]
            )

        intel_table = Table(
            intelligence_rows,
            colWidths=[
                75 * mm,
                80 * mm,
            ],
        )

        intel_table.setStyle(
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
                        7.5,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                ]
            )
        )

        story.append(intel_table)

        story.append(Spacer(1, 10))

        story.append(
            Paragraph(
                "Trend indicator: → is shown where historical "
                "comparison is unavailable in the company-level "
                "cash-flow intelligence dataset. N/A indicates "
                "unavailable source data.",
                styles["SmallText"],
            )
        )

        story.append(PageBreak())

    doc.build(story)

    return output_path


def main():

    print("=" * 70)
    print("SPRINT 5 - DAY 35")
    print("PORTFOLIO SUMMARY REPORT")
    print("=" * 70)
    print()

    data = load_data()

    companies = data["companies"]

    print(
        f"Company universe: {len(companies)}"
    )

    output = generate_portfolio_report(data)

    print()
    print(
        f"Created: {output}"
    )

    from pypdf import PdfReader

    reader = PdfReader(str(output))

    actual_pages = len(reader.pages)
    expected_pages = len(companies) + 1

    print(
        f"Expected pages: {expected_pages}"
    )

    print(
        f"Actual pages  : {actual_pages}"
    )

    file_size = output.stat().st_size

    print(
        f"File size     : {file_size / 1024:.1f} KB"
    )

    if len(companies) != 92:
        raise RuntimeError(
            f"Expected 92 companies, found {len(companies)}"
        )

    if actual_pages != expected_pages:
        raise RuntimeError(
            f"Expected {expected_pages} pages, "
            f"found {actual_pages}"
        )

    if file_size < 30_000:
        raise RuntimeError(
            "Portfolio PDF is unexpectedly small."
        )

    print()
    print("=" * 70)
    print("DAY 35 VALIDATION: PASS")
    print("=" * 70)
    print()
    print("92 companies covered.")
    print("Alphabetical portfolio pages generated.")
    print("6 KPIs per company.")
    print("Cash-flow intelligence included.")
    print("Capital allocation included.")
    print("Portfolio PDF validation passed.")
    print()
    print("SPRINT 5 COMPLETE")


if __name__ == "__main__":
    main()