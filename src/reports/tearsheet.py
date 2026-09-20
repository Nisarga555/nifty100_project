"""
Sprint 5 - Day 33
Company Tearsheet PDF Generator

Creates a 2-page company tearsheet using ReportLab.

Page 1:
    - Company header
    - 6 KPI tiles
    - 10-year Revenue / Net Profit bar chart
    - ROE / ROCE trend

Page 2:
    - Balance Sheet composition table
    - Cash Flow waterfall
    - Capital Allocation badge
    - Pros / Cons
    - Historical Financial Snapshot

QA companies:
    TCS
    HDFCBANK
    RELIANCE
    SUNPHARMA
    TATASTEEL
"""

import math
import re
from pathlib import Path

import pandas as pd
from reportlab.graphics.charts.barcharts import (
    VerticalBarChart,
)
from reportlab.graphics.shapes import (
    Drawing,
    Line,
    Rect,
    String,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# =====================================================================
# PATHS
# =====================================================================

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "reports" / "tearsheets"

OUTPUT.mkdir(
    parents=True,
    exist_ok=True,
)


# =====================================================================
# SOURCE FILES
# =====================================================================

COMPANIES_FILE = RAW / "companies.xlsx"
SECTORS_FILE = RAW / "sectors.xlsx"
PL_FILE = RAW / "profitandloss.xlsx"
BS_FILE = RAW / "balancesheet.xlsx"
CF_FILE = RAW / "cashflow.xlsx"

PROS_CONS_FILE = ROOT / "output" / "pros_cons_generated.csv"

CASHFLOW_INTELLIGENCE_FILE = ROOT / "output" / "cashflow_intelligence.xlsx"


# =====================================================================
# COLORS
# =====================================================================

NAVY = colors.HexColor("#0B1F3A")
BLUE = colors.HexColor("#17365D")
LIGHT_BLUE = colors.HexColor("#EAF1F8")
LIGHT_GREY = colors.HexColor("#F2F4F7")
MID_GREY = colors.HexColor("#667085")
DARK = colors.HexColor("#1D2939")
GREEN = colors.HexColor("#198754")
LIGHT_GREEN = colors.HexColor("#E9F7EF")
RED = colors.HexColor("#B42318")
LIGHT_RED = colors.HexColor("#FDECEC")
WHITE = colors.white


# =====================================================================
# HELPERS
# =====================================================================


def safe_float(value):
    if value is None:
        return None

    try:
        value = float(value)

        if math.isnan(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def fmt_number(value, decimals=1):
    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}"


def fmt_pct(value, decimals=1):
    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"{value:.{decimals}f}%"


def normalize_company_id(value):
    if value is None:
        return None

    text = str(value).strip().upper()

    if not text or text == "NAN":
        return None

    return text


def normalize_year(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    match = re.search(
        r"(20\d{2})",
        text,
    )

    if match:
        return int(match.group(1))

    match = re.search(
        r"(?:-| )(\d{2})$",
        text,
    )

    if match:
        yy = int(match.group(1))

        if yy >= 50:
            return 1900 + yy

        return 2000 + yy

    return None


# =====================================================================
# DATA LOADING
# =====================================================================


def load_data():

    companies = pd.read_excel(
        COMPANIES_FILE,
        header=1,
    )

    sectors = pd.read_excel(
        SECTORS_FILE,
        header=0,
    )

    pl = pd.read_excel(
        PL_FILE,
        header=1,
    )

    bs = pd.read_excel(
        BS_FILE,
        header=1,
    )

    cf = pd.read_excel(
        CF_FILE,
        header=1,
    )

    pros_cons = pd.read_csv(PROS_CONS_FILE)

    intelligence = pd.read_excel(CASHFLOW_INTELLIGENCE_FILE)

    # ---------------------------------------------------------------
    # Normalize IDs
    # ---------------------------------------------------------------

    for df in (
        companies,
        sectors,
        pl,
        bs,
        cf,
        pros_cons,
        intelligence,
    ):

        if "company_id" in df.columns:

            df["company_id"] = df["company_id"].apply(normalize_company_id)

    # Companies uses "id" rather than company_id.
    if "id" in companies.columns:

        companies["id"] = companies["id"].apply(normalize_company_id)

    # ---------------------------------------------------------------
    # Normalize years
    # ---------------------------------------------------------------

    for df in (
        pl,
        bs,
        cf,
    ):

        df["year_num"] = df["year"].apply(normalize_year)

        df.dropna(
            subset=["year_num"],
            inplace=True,
        )

        df["year_num"] = df["year_num"].astype(int)

    # ---------------------------------------------------------------
    # Numeric columns
    # ---------------------------------------------------------------

    for column in [
        "sales",
        "net_profit",
        "operating_profit",
        "eps",
    ]:

        pl[column] = pd.to_numeric(
            pl[column],
            errors="coerce",
        )

    for column in [
        "equity_capital",
        "reserves",
        "borrowings",
        "other_liabilities",
        "total_assets",
    ]:

        bs[column] = pd.to_numeric(
            bs[column],
            errors="coerce",
        )

    for column in [
        "operating_activity",
        "investing_activity",
        "financing_activity",
        "net_cash_flow",
    ]:

        cf[column] = pd.to_numeric(
            cf[column],
            errors="coerce",
        )

    return {
        "companies": companies,
        "sectors": sectors,
        "pl": pl,
        "bs": bs,
        "cf": cf,
        "pros_cons": pros_cons,
        "intelligence": intelligence,
    }


# =====================================================================
# STYLES
# =====================================================================


def build_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=21,
            textColor=WHITE,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=NAVY,
            spaceBefore=2,
            spaceAfter=3,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=DARK,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Tiny",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=6,
            leading=7.5,
            textColor=MID_GREY,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BulletPro",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=6.7,
            leading=8.5,
            textColor=GREEN,
            leftIndent=7,
            firstLineIndent=-5,
            spaceAfter=2,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BulletCon",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=6.7,
            leading=8.5,
            textColor=RED,
            leftIndent=7,
            firstLineIndent=-5,
            spaceAfter=2,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TileLabel",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=6,
            leading=7,
            textColor=MID_GREY,
            alignment=1,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TileValue",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=NAVY,
            alignment=1,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Badge",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=NAVY,
            alignment=1,
        )
    )

    return styles


# =====================================================================
# PAGE BACKGROUND
# =====================================================================


def draw_page_background(
    canvas,
    doc,
):

    canvas.saveState()

    canvas.setFillColor(colors.HexColor("#F8FAFC"))

    canvas.rect(
        0,
        0,
        A4[0],
        A4[1],
        stroke=0,
        fill=1,
    )

    canvas.restoreState()


# =====================================================================
# COMPANY HEADER
# =====================================================================


def company_header(
    company_name,
    ticker,
    sector,
    styles,
):

    header_data = [
        [
            Paragraph(
                company_name,
                styles["ReportTitle"],
            ),
            Paragraph(
                f"<b>{ticker}</b><br/>{sector}",
                ParagraphStyle(
                    "HeaderRight",
                    parent=styles["Small"],
                    textColor=WHITE,
                    alignment=2,
                    leading=9,
                ),
            ),
        ]
    ]

    table = Table(
        header_data,
        colWidths=[
            125 * mm,
            50 * mm,
        ],
        rowHeights=[
            17 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    NAVY,
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
                    6 * mm,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6 * mm,
                ),
            ]
        )
    )

    return table


# =====================================================================
# KPI TILES
# =====================================================================


def kpi_tiles(
    metrics,
    styles,
):

    rows = []

    for i in range(
        0,
        6,
        3,
    ):

        row = []

        for label, value in metrics[i : i + 3]:

            cell = [
                Paragraph(
                    label,
                    styles["TileLabel"],
                ),
                Spacer(
                    1,
                    1 * mm,
                ),
                Paragraph(
                    value,
                    styles["TileValue"],
                ),
            ]

            row.append(cell)

        rows.append(row)

    table = Table(
        rows,
        colWidths=[
            57 * mm,
            57 * mm,
            57 * mm,
        ],
        rowHeights=[
            20 * mm,
            20 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    WHITE,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
            ]
        )
    )

    return table


# =====================================================================
# REVENUE / PROFIT CHART
# =====================================================================


def revenue_profit_chart(
    pl,
):

    drawing = Drawing(
        178 * mm,
        65 * mm,
    )

    data = (
        pl[
            [
                "year_num",
                "sales",
                "net_profit",
            ]
        ]
        .drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
        .tail(10)
    )

    if data.empty:
        return drawing

    sales = [0 if pd.isna(x) else float(x) for x in data["sales"]]

    profit = [0 if pd.isna(x) else float(x) for x in data["net_profit"]]

    chart = VerticalBarChart()

    chart.x = 12 * mm
    chart.y = 10 * mm
    chart.width = 145 * mm
    chart.height = 45 * mm

    chart.data = [
        sales,
        profit,
    ]

    chart.categoryAxis.categoryNames = [str(int(x)) for x in data["year_num"]]

    chart.categoryAxis.labels.fontSize = 5
    chart.categoryAxis.labels.angle = 45

    chart.valueAxis.labels.fontSize = 5

    chart.barWidth = 3
    chart.groupSpacing = 5

    chart.bars[0].fillColor = BLUE
    chart.bars[1].fillColor = GREEN

    drawing.add(chart)

    drawing.add(
        String(
            15 * mm,
            59 * mm,
            "Revenue vs Net Profit (₹ Cr)",
            fontName="Helvetica-Bold",
            fontSize=8,
            fillColor=NAVY,
        )
    )

    drawing.add(
        String(
            112 * mm,
            59 * mm,
            "Revenue",
            fontName="Helvetica",
            fontSize=6,
            fillColor=BLUE,
        )
    )

    drawing.add(
        String(
            137 * mm,
            59 * mm,
            "Net Profit",
            fontName="Helvetica",
            fontSize=6,
            fillColor=GREEN,
        )
    )

    return drawing


# =====================================================================
# ROE / ROCE TREND
# =====================================================================


def roe_roce_chart(
    ratios,
):

    drawing = Drawing(
        178 * mm,
        65 * mm,
    )

    if ratios.empty:
        return drawing

    data = (
        ratios[
            [
                "year_num",
                "roe",
                "roce",
            ]
        ]
        .drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
        .tail(10)
    )

    values = []

    for value in data["roe"]:
        value = safe_float(value)

        if value is not None:
            values.append(value)

    for value in data["roce"]:
        value = safe_float(value)

        if value is not None:
            values.append(value)

    if not values:
        return drawing

    x0 = 18 * mm
    y0 = 10 * mm
    width = 145 * mm
    height = 42 * mm

    ymin = min(
        0,
        min(values),
    )

    ymax = max(
        10,
        max(values),
    )

    span = ymax - ymin

    if span == 0:
        span = 1

    def px(index):

        if len(data) <= 1:
            return x0 + width / 2

        return x0 + width * index / (len(data) - 1)

    def py(value):

        if value is None:
            return None

        return y0 + height * (value - ymin) / span

    drawing.add(
        String(
            15 * mm,
            59 * mm,
            "ROE / ROCE Trend",
            fontName="Helvetica-Bold",
            fontSize=8,
            fillColor=NAVY,
        )
    )

    previous_roe = None
    previous_roce = None

    for index, row in data.reset_index(drop=True).iterrows():

        x = px(index)

        roe = safe_float(row["roe"])

        roce = safe_float(row["roce"])

        if previous_roe is not None and roe is not None:

            drawing.add(
                Line(
                    px(index - 1),
                    py(previous_roe),
                    x,
                    py(roe),
                    strokeColor=BLUE,
                    strokeWidth=1.2,
                )
            )

        if previous_roce is not None and roce is not None:

            drawing.add(
                Line(
                    px(index - 1),
                    py(previous_roce),
                    x,
                    py(roce),
                    strokeColor=GREEN,
                    strokeWidth=1.2,
                )
            )

        previous_roe = roe
        previous_roce = roce

        drawing.add(
            String(
                x,
                y0 - 7,
                str(int(row["year_num"])),
                fontName="Helvetica",
                fontSize=5,
                textAnchor="middle",
                fillColor=MID_GREY,
            )
        )

    drawing.add(
        String(
            122 * mm,
            59 * mm,
            "ROE",
            fontName="Helvetica",
            fontSize=6,
            fillColor=BLUE,
        )
    )

    drawing.add(
        String(
            143 * mm,
            59 * mm,
            "ROCE",
            fontName="Helvetica",
            fontSize=6,
            fillColor=GREEN,
        )
    )

    return drawing


# =====================================================================
# BALANCE SHEET TABLE
# =====================================================================


def balance_sheet_table(
    bs,
    styles,
):

    data = (
        bs[
            [
                "year_num",
                "equity_capital",
                "reserves",
                "borrowings",
                "other_liabilities",
            ]
        ]
        .drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
        .tail(8)
    )

    if data.empty:

        return Paragraph(
            "Balance-sheet data unavailable.",
            styles["Small"],
        )

    rows = [
        [
            Paragraph(
                "<b>Year</b>",
                styles["Tiny"],
            ),
            Paragraph(
                "<b>Equity + Reserves</b>",
                styles["Tiny"],
            ),
            Paragraph(
                "<b>Borrowings</b>",
                styles["Tiny"],
            ),
            Paragraph(
                "<b>Other Liabilities</b>",
                styles["Tiny"],
            ),
        ]
    ]

    for _, row in data.iterrows():

        equity = safe_float(row["equity_capital"]) or 0

        reserves = safe_float(row["reserves"]) or 0

        borrowings = safe_float(row["borrowings"]) or 0

        other = safe_float(row["other_liabilities"]) or 0

        rows.append(
            [
                str(int(row["year_num"])),
                fmt_number(equity + reserves),
                fmt_number(borrowings),
                fmt_number(other),
            ]
        )

    table = Table(
        rows,
        colWidths=[
            25 * mm,
            48 * mm,
            42 * mm,
            54 * mm,
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
                    NAVY,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    WHITE,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        WHITE,
                        LIGHT_GREY,
                    ],
                ),
                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "RIGHT",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    6,
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
                    1.5 * mm,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    1.5 * mm,
                ),
            ]
        )
    )

    return table


# =====================================================================
# CASH FLOW WATERFALL
# =====================================================================


def cashflow_waterfall(
    latest_cf,
):

    drawing = Drawing(
        178 * mm,
        58 * mm,
    )

    if latest_cf is None:
        return drawing

    values = [
        (
            "CFO",
            safe_float(latest_cf.get("operating_activity")),
        ),
        (
            "CFI",
            safe_float(latest_cf.get("investing_activity")),
        ),
        (
            "CFF",
            safe_float(latest_cf.get("financing_activity")),
        ),
        (
            "Net Cash",
            safe_float(latest_cf.get("net_cash_flow")),
        ),
    ]

    valid = [value for _, value in values if value is not None]

    if not valid:
        return drawing

    maximum = max(abs(value) for value in valid)

    if maximum == 0:
        maximum = 1

    base_y = 18 * mm
    chart_height = 25 * mm
    bar_width = 22 * mm
    gap = 14 * mm

    drawing.add(
        String(
            15 * mm,
            52 * mm,
            "Latest Cash Flow (₹ Cr)",
            fontName="Helvetica-Bold",
            fontSize=8,
            fillColor=NAVY,
        )
    )

    for index, (
        label,
        value,
    ) in enumerate(values):

        if value is None:
            continue

        x = 18 * mm + index * (bar_width + gap)

        height = abs(value) / maximum * chart_height

        if value >= 0:
            y = base_y
        else:
            y = base_y - height

        fill = GREEN if value >= 0 else RED

        drawing.add(
            Rect(
                x,
                y,
                bar_width,
                height,
                fillColor=fill,
                strokeColor=fill,
            )
        )

        drawing.add(
            String(
                x + bar_width / 2,
                y + height + 2,
                fmt_number(value),
                fontName="Helvetica-Bold",
                fontSize=5.5,
                textAnchor="middle",
                fillColor=DARK,
            )
        )

        drawing.add(
            String(
                x + bar_width / 2,
                base_y - 7,
                label,
                fontName="Helvetica",
                fontSize=6,
                textAnchor="middle",
                fillColor=MID_GREY,
            )
        )

    drawing.add(
        Line(
            12 * mm,
            base_y,
            166 * mm,
            base_y,
            strokeColor=MID_GREY,
            strokeWidth=0.5,
        )
    )

    return drawing


# =====================================================================
# PROS / CONS
# =====================================================================


def pros_cons_section(
    company_id,
    pros_cons,
    styles,
):

    rows = pros_cons[pros_cons["company_id"] == company_id].copy()

    pros = (
        rows[rows["type"].astype(str).str.lower() == "pro"]
        .sort_values(
            "confidence_pct",
            ascending=False,
        )
        .head(4)
    )

    cons = (
        rows[rows["type"].astype(str).str.lower() == "con"]
        .sort_values(
            "confidence_pct",
            ascending=False,
        )
        .head(4)
    )

    pro_flow = [
        Paragraph(
            "<b>Pros</b>",
            styles["Section"],
        )
    ]

    if pros.empty:

        pro_flow.append(
            Paragraph(
                "No generated pros available.",
                styles["Small"],
            )
        )

    else:

        for _, row in pros.iterrows():

            confidence = fmt_number(
                row.get("confidence_pct"),
                0,
            )

            text = str(
                row.get(
                    "text",
                    "",
                )
            )

            pro_flow.append(
                Paragraph(
                    f"• {text} "
                    f"<font color='#667085'>"
                    f"({confidence}%)"
                    f"</font>",
                    styles["BulletPro"],
                )
            )

    con_flow = [
        Paragraph(
            "<b>Cons</b>",
            styles["Section"],
        )
    ]

    if cons.empty:

        con_flow.append(
            Paragraph(
                "No generated cons available.",
                styles["Small"],
            )
        )

    else:

        for _, row in cons.iterrows():

            confidence = fmt_number(
                row.get("confidence_pct"),
                0,
            )

            text = str(
                row.get(
                    "text",
                    "",
                )
            )

            con_flow.append(
                Paragraph(
                    f"• {text} "
                    f"<font color='#667085'>"
                    f"({confidence}%)"
                    f"</font>",
                    styles["BulletCon"],
                )
            )

    table = Table(
        [
            [
                pro_flow,
                con_flow,
            ]
        ],
        colWidths=[
            87 * mm,
            87 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, 0),
                    LIGHT_GREEN,
                ),
                (
                    "BACKGROUND",
                    (1, 0),
                    (1, 0),
                    LIGHT_RED,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    3 * mm,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3 * mm,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2 * mm,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2 * mm,
                ),
            ]
        )
    )

    return table


# =====================================================================
# HISTORICAL FINANCIAL SNAPSHOT
# =====================================================================


def historical_snapshot(
    company_pl,
    company_cf,
    styles,
):

    history = company_pl.merge(
        company_cf[
            [
                "year_num",
                "operating_activity",
                "investing_activity",
                "financing_activity",
            ]
        ],
        on="year_num",
        how="left",
    )

    history = (
        history.drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
        .tail(7)
    )

    if history.empty:

        return Paragraph(
            "Historical financial data unavailable.",
            styles["Small"],
        )

    rows = [
        [
            Paragraph("<b>Year</b>", styles["Tiny"]),
            Paragraph("<b>Revenue</b>", styles["Tiny"]),
            Paragraph("<b>Net Profit</b>", styles["Tiny"]),
            Paragraph("<b>EPS</b>", styles["Tiny"]),
            Paragraph("<b>CFO</b>", styles["Tiny"]),
            Paragraph("<b>CFI</b>", styles["Tiny"]),
            Paragraph("<b>CFF</b>", styles["Tiny"]),
        ]
    ]

    for _, row in history.iterrows():

        rows.append(
            [
                str(int(row["year_num"])),
                fmt_number(row.get("sales")),
                fmt_number(row.get("net_profit")),
                fmt_number(row.get("eps"), 2),
                fmt_number(row.get("operating_activity")),
                fmt_number(row.get("investing_activity")),
                fmt_number(row.get("financing_activity")),
            ]
        )

    table = Table(
        rows,
        colWidths=[
            20 * mm,
            29 * mm,
            29 * mm,
            21 * mm,
            29 * mm,
            29 * mm,
            29 * mm,
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
                    NAVY,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    WHITE,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#D0D5DD"),
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        WHITE,
                        LIGHT_GREY,
                    ],
                ),
                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "RIGHT",
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
                    1.1 * mm,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    1.1 * mm,
                ),
            ]
        )
    )

    return table


# =====================================================================
# TEARSHEET BUILDER
# =====================================================================


def build_tearsheet(
    company_id,
    data,
):

    styles = build_styles()

    companies = data["companies"]
    sectors = data["sectors"]
    pl = data["pl"]
    bs = data["bs"]
    cf = data["cf"]
    pros_cons = data["pros_cons"]
    intelligence = data["intelligence"]

    # ---------------------------------------------------------------
    # Company
    # ---------------------------------------------------------------

    company_rows = companies[companies["id"] == company_id]

    if company_rows.empty:
        return None

    company = company_rows.iloc[0]

    company_name = str(
        company.get(
            "company_name",
            company_id,
        )
    )

    sector_rows = sectors[sectors["company_id"] == company_id]

    sector = (
        str(sector_rows.iloc[0]["broad_sector"]) if not sector_rows.empty else "Unknown"
    )

    # ---------------------------------------------------------------
    # Company financial data
    # ---------------------------------------------------------------

    company_pl = (
        pl[pl["company_id"] == company_id]
        .drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
    )

    company_bs = (
        bs[bs["company_id"] == company_id]
        .drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
    )

    company_cf = (
        cf[cf["company_id"] == company_id]
        .drop_duplicates(
            "year_num",
            keep="last",
        )
        .sort_values("year_num")
    )

    years = []

    for df in [
        company_pl,
        company_bs,
        company_cf,
    ]:

        if not df.empty:
            years.extend(df["year_num"].tolist())

    if not years:
        return None

    latest_year = max(years)

    # ---------------------------------------------------------------
    # Latest records
    # ---------------------------------------------------------------

    pl_rows = company_pl[company_pl["year_num"] == latest_year]

    bs_rows = company_bs[company_bs["year_num"] == latest_year]

    cf_rows = company_cf[company_cf["year_num"] == latest_year]

    pl_latest = pl_rows.iloc[-1] if not pl_rows.empty else None

    cf_latest = cf_rows.iloc[-1] if not cf_rows.empty else None

    # ---------------------------------------------------------------
    # ROE / ROCE history
    # ---------------------------------------------------------------

    ratio_records = []

    for _, row in company_pl.iterrows():

        year = int(row["year_num"])

        bs_rows_year = company_bs[company_bs["year_num"] == year]

        if bs_rows_year.empty:
            continue

        bs_row = bs_rows_year.iloc[-1]

        net_profit = safe_float(row["net_profit"])

        equity = safe_float(bs_row["equity_capital"])

        reserves = safe_float(bs_row["reserves"])

        borrowings = safe_float(bs_row["borrowings"])

        roe = None

        if (
            net_profit is not None
            and equity is not None
            and reserves is not None
            and equity + reserves > 0
        ):

            roe = net_profit / (equity + reserves) * 100

        roce = None

        operating_profit = safe_float(row["operating_profit"])

        if (
            operating_profit is not None
            and equity is not None
            and reserves is not None
            and borrowings is not None
            and (equity + reserves + borrowings) > 0
        ):

            roce = operating_profit / (equity + reserves + borrowings) * 100

        ratio_records.append(
            {
                "year_num": year,
                "roe": roe,
                "roce": roce,
            }
        )

    ratios = pd.DataFrame(ratio_records)

    # ---------------------------------------------------------------
    # Latest KPI values
    # ---------------------------------------------------------------

    latest_sales = pl_latest["sales"] if pl_latest is not None else None

    latest_profit = pl_latest["net_profit"] if pl_latest is not None else None

    latest_eps = pl_latest["eps"] if pl_latest is not None else None

    latest_roe = None
    latest_roce = None

    if not ratios.empty:

        latest_ratio = ratios[ratios["year_num"] == latest_year]

        if not latest_ratio.empty:

            latest_roe = latest_ratio.iloc[-1]["roe"]

            latest_roce = latest_ratio.iloc[-1]["roce"]

    if latest_roe is None:

        latest_roe = safe_float(company.get("roe_percentage"))

    if latest_roce is None:

        latest_roce = safe_float(company.get("roce_percentage"))

    metrics = [
        (
            "Revenue",
            (f"₹{fmt_number(latest_sales)} Cr" if latest_sales is not None else "N/A"),
        ),
        (
            "Net Profit",
            (
                f"₹{fmt_number(latest_profit)} Cr"
                if latest_profit is not None
                else "N/A"
            ),
        ),
        (
            "EPS",
            fmt_number(
                latest_eps,
                2,
            ),
        ),
        (
            "ROE",
            fmt_pct(latest_roe),
        ),
        (
            "ROCE",
            fmt_pct(latest_roce),
        ),
        (
            "Latest Year",
            str(latest_year),
        ),
    ]

    # ---------------------------------------------------------------
    # Document
    # ---------------------------------------------------------------

    filename = OUTPUT / f"{company_id}_tearsheet.pdf"

    doc = BaseDocTemplate(
        str(filename),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"{company_name} Tearsheet",
        author="Nifty 100 Analytics",
    )

    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="normal",
    )

    doc.addPageTemplates(
        [
            PageTemplate(
                id="main",
                frames=frame,
                onPage=draw_page_background,
            )
        ]
    )

    story = []

    # ===============================================================
    # PAGE 1
    # ===============================================================

    story.append(
        company_header(
            company_name,
            company_id,
            sector,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )

    story.append(
        kpi_tiles(
            metrics,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            2 * mm,
        )
    )

    story.append(revenue_profit_chart(company_pl))

    story.append(
        Spacer(
            1,
            1 * mm,
        )
    )

    story.append(roe_roce_chart(ratios))

    story.append(PageBreak())

    # ===============================================================
    # PAGE 2
    # ===============================================================

    story.append(
        Paragraph(
            "Balance Sheet Composition",
            styles["Section"],
        )
    )

    story.append(
        balance_sheet_table(
            company_bs,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            2 * mm,
        )
    )

    story.append(
        Paragraph(
            "Cash Flow Waterfall",
            styles["Section"],
        )
    )

    story.append(
        cashflow_waterfall(cf_latest.to_dict() if cf_latest is not None else None)
    )

    story.append(
        Spacer(
            1,
            1 * mm,
        )
    )

    # ---------------------------------------------------------------
    # Capital Allocation
    # ---------------------------------------------------------------

    allocation = "N/A"

    intelligence_rows = intelligence[intelligence["company_id"] == company_id]

    if not intelligence_rows.empty:

        value = intelligence_rows.iloc[0].get("capital_allocation_label")

        if value is not None and str(value) not in [
            "nan",
            "None",
        ]:

            allocation = str(value)

    badge = Table(
        [
            [
                Paragraph(
                    "CAPITAL ALLOCATION",
                    styles["Tiny"],
                ),
                Paragraph(
                    allocation,
                    styles["Badge"],
                ),
            ]
        ],
        colWidths=[
            48 * mm,
            120 * mm,
        ],
    )

    badge.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, 0),
                    LIGHT_BLUE,
                ),
                (
                    "BACKGROUND",
                    (1, 0),
                    (1, 0),
                    WHITE,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#D0D5DD"),
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
                    3 * mm,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3 * mm,
                ),
            ]
        )
    )

    story.append(badge)

    story.append(
        Spacer(
            1,
            2 * mm,
        )
    )

    # ---------------------------------------------------------------
    # Pros / Cons
    # ---------------------------------------------------------------

    story.append(
        pros_cons_section(
            company_id,
            pros_cons,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            2 * mm,
        )
    )

    # ---------------------------------------------------------------
    # Historical Snapshot
    # ---------------------------------------------------------------

    story.append(
        Paragraph(
            "Historical Financial Snapshot",
            styles["Section"],
        )
    )

    story.append(
        historical_snapshot(
            company_pl,
            company_cf,
            styles,
        )
    )

    # ---------------------------------------------------------------
    # Build
    # ---------------------------------------------------------------

    doc.build(story)

    return filename


# =====================================================================
# GENERATE SELECTED COMPANIES
# =====================================================================


def generate_for_companies(
    company_ids,
):

    data = load_data()

    generated = []
    skipped = []

    for company_id in company_ids:

        company_id = normalize_company_id(company_id)

        try:

            result = build_tearsheet(
                company_id,
                data,
            )

            if result is None:

                skipped.append(
                    (
                        company_id,
                        "No usable annual financial data",
                    )
                )

            else:

                generated.append(result)

        except Exception as exc:

            skipped.append(
                (
                    company_id,
                    str(exc),
                )
            )

    return generated, skipped


# =====================================================================
# DAY 33 QA
# =====================================================================

if __name__ == "__main__":

    test_companies = [
        "TCS",
        "HDFCBANK",
        "RELIANCE",
        "SUNPHARMA",
        "TATASTEEL",
    ]

    print()
    print("=" * 70)
    print("SPRINT 5 - DAY 33")
    print("TEARSHEET PDF QA")
    print("=" * 70)
    print()

    generated, skipped = generate_for_companies(test_companies)

    print()
    print(f"Generated: {len(generated)}")

    for path in generated:

        size_kb = path.stat().st_size / 1024

        print(f"  {path.name}: " f"{size_kb:.1f} KB")

    print()

    if skipped:

        print("SKIPPED / FAILED:")

        for company_id, reason in skipped:

            print(f"  {company_id}: " f"{reason}")

    print()

    if len(generated) != 5:

        raise AssertionError(
            f"Expected 5 test tearsheets, " f"generated {len(generated)}."
        )

    print("VALIDATION: " "5-company PDF generation PASS")

    print()
