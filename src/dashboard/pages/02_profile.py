import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_pl,
    get_pros_cons,
    get_ratios,
    get_sectors,
    extract_year,
)


st.set_page_config(
    page_title="Company Profile | Nifty 100 Analytics",
    page_icon="👤",
    layout="wide",
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def format_metric(value, suffix=""):
    value = numeric(value)

    if pd.isna(value):
        return "N/A"

    return f"{value:,.2f}{suffix}"


def sort_by_year(dataframe):
    """Sort source data chronologically."""
    if dataframe.empty:
        return dataframe

    data = dataframe.copy()

    if "year" in data.columns:
        data["_parsed_year"] = data["year"].apply(
            extract_year
        )

        data = data.sort_values(
            "_parsed_year",
            na_position="last",
        )

    return data


def find_column(dataframe, candidates):
    """Find the first available column from a candidate list."""
    for column in candidates:
        if column in dataframe.columns:
            return column

    return None


# ---------------------------------------------------------------------
# Load master data
# ---------------------------------------------------------------------

companies = get_companies()
sectors = get_sectors()

if companies.empty:
    st.error(
        "Company master data could not be loaded."
    )
    st.stop()


# ---------------------------------------------------------------------
# Build company lookup
# ---------------------------------------------------------------------

company_lookup = companies.copy()

company_lookup["ticker"] = (
    company_lookup["id"]
    .astype(str)
    .str.strip()
    .str.upper()
)

company_names = (
    company_lookup["company_name"]
    .fillna("")
    .astype(str)
)

company_lookup["search_label"] = (
    company_lookup["ticker"]
    + " — "
    + company_names
)


# ---------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------

st.title("👤 Company Profile")
st.caption(
    "Explore financial performance, profitability, "
    "growth and business strengths."
)


# ---------------------------------------------------------------------
# Search / autocomplete
# ---------------------------------------------------------------------

search_text = st.text_input(
    "🔎 Search company or ticker",
    placeholder="Type a company name or ticker, e.g. TCS",
)


if search_text.strip():
    query = search_text.strip().lower()

    matches = company_lookup[
        company_lookup["ticker"].str.lower().str.contains(
            query,
            na=False,
        )
        | company_lookup["company_name"]
        .astype(str)
        .str.lower()
        .str.contains(
            query,
            na=False,
        )
    ].copy()

else:
    matches = company_lookup.copy()


if matches.empty:
    st.warning(
        "Ticker not found — please try another"
    )
    st.stop()


# Limit autocomplete list for clean UI
matches = matches.head(20)

selected_label = st.selectbox(
    "Select company",
    matches["search_label"].tolist(),
)


ticker = selected_label.split(" — ")[0].strip().upper()


# ---------------------------------------------------------------------
# Fetch company data
# ---------------------------------------------------------------------

company_rows = company_lookup[
    company_lookup["ticker"] == ticker
]

if company_rows.empty:
    st.warning(
        "Ticker not found — please try another"
    )
    st.stop()


company = company_rows.iloc[0]

ratios = sort_by_year(
    get_ratios(ticker)
)

pl = sort_by_year(
    get_pl(ticker)
)

pros_cons = get_pros_cons(ticker)

sector_rows = sectors[
    sectors["company_id"]
    .astype(str)
    .str.strip()
    .str.upper()
    == ticker
].copy() if (
    not sectors.empty
    and "company_id" in sectors.columns
) else pd.DataFrame()


# ---------------------------------------------------------------------
# Sector information
# ---------------------------------------------------------------------

sector = (
    sector_rows.iloc[0]["broad_sector"]
    if not sector_rows.empty
    and "broad_sector" in sector_rows.columns
    else "N/A"
)

sub_sector = (
    sector_rows.iloc[0]["sub_sector"]
    if not sector_rows.empty
    and "sub_sector" in sector_rows.columns
    else "N/A"
)


# ---------------------------------------------------------------------
# Company card
# ---------------------------------------------------------------------

st.subheader(
    f"{company.get('company_name', ticker)} ({ticker})"
)

card1, card2, card3, card4 = st.columns(4)

with card1:
    st.markdown("**Sector**")
    st.write(sector)

with card2:
    st.markdown("**Sub-sector**")
    st.write(sub_sector)

with card3:
    st.markdown("**NSE Ticker**")
    st.write(ticker)

with card4:
    website = company.get("website")

    if pd.notna(website) and str(website).strip():
        st.markdown("**Website**")
        st.markdown(
            f"[Visit company website]({website})"
        )
    else:
        st.markdown("**Website**")
        st.write("N/A")


about = company.get("about_company")

if pd.notna(about) and str(about).strip():
    st.markdown("### About the Company")
    st.write(str(about))


# ---------------------------------------------------------------------
# Latest available KPI row
# ---------------------------------------------------------------------

latest_ratio = (
    ratios.dropna(
        subset=["_parsed_year"]
    ).iloc[-1]
    if not ratios.empty
    and "_parsed_year" in ratios.columns
    and ratios["_parsed_year"].notna().any()
    else None
)


if latest_ratio is not None:

    roe = latest_ratio.get(
        "return_on_equity_pct"
    )

    roce = latest_ratio.get(
        "return_on_capital_employed_pct"
    )

    npm = latest_ratio.get(
        "net_profit_margin_pct"
    )

    de = latest_ratio.get(
        "debt_to_equity"
    )

    revenue_cagr = latest_ratio.get(
        "revenue_cagr_5yr"
    )

    fcf = latest_ratio.get(
        "free_cash_flow_cr"
    )

else:
    roe = roce = npm = de = revenue_cagr = fcf = np.nan


st.divider()

st.subheader("📊 Key Financial Metrics")

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.metric(
        "ROE",
        format_metric(roe, "%"),
    )

with k2:
    st.metric(
        "ROCE",
        format_metric(roce, "%"),
    )

with k3:
    st.metric(
        "Net Profit Margin",
        format_metric(npm, "%"),
    )

with k4:
    st.metric(
        "Debt / Equity",
        format_metric(de),
    )

with k5:
    st.metric(
        "Revenue CAGR 5Y",
        format_metric(revenue_cagr, "%"),
    )

with k6:
    st.metric(
        "FCF",
        format_metric(fcf, " Cr"),
    )


# ---------------------------------------------------------------------
# Revenue + Net Profit chart
# ---------------------------------------------------------------------

st.divider()

st.subheader("📈 Revenue & Net Profit — 10 Year Trend")

if not pl.empty:

    revenue_col = find_column(
        pl,
        ["sales", "revenue"],
    )

    profit_col = find_column(
        pl,
        ["net_profit"],
    )

    if revenue_col or profit_col:

        chart_data = pl.copy()

        chart_data["Year"] = chart_data[
            "year"
        ].astype(str)

        if revenue_col:
            chart_data["Revenue"] = pd.to_numeric(
                chart_data[revenue_col],
                errors="coerce",
            )

        if profit_col:
            chart_data["Net Profit"] = pd.to_numeric(
                chart_data[profit_col],
                errors="coerce",
            )

        chart_data = chart_data.tail(10)

        fig = go.Figure()

        if revenue_col:
            fig.add_trace(
                go.Bar(
                    x=chart_data["Year"],
                    y=chart_data["Revenue"],
                    name="Revenue",
                )
            )

        if profit_col:
            fig.add_trace(
                go.Bar(
                    x=chart_data["Year"],
                    y=chart_data["Net Profit"],
                    name="Net Profit",
                )
            )

        fig.update_layout(
            barmode="group",
            height=430,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
            xaxis_title="Year",
            yaxis_title="₹ Crore",
            legend_title="Metric",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:
        st.info(
            "Revenue / Net Profit data unavailable."
        )

else:
    st.info(
        "Financial history is not available for this company."
    )


# ---------------------------------------------------------------------
# ROE + ROCE chart
# ---------------------------------------------------------------------

st.subheader("📊 ROE vs ROCE — 10 Year Trend")

if not ratios.empty:

    roe_col = "return_on_equity_pct"

    roce_col = "return_on_capital_employed_pct"

    if roe_col in ratios.columns or roce_col in ratios.columns:

        chart = ratios.tail(10).copy()

        chart["Year"] = chart[
            "year"
        ].astype(str)

        fig = go.Figure()

        if roe_col in chart.columns:
            fig.add_trace(
                go.Scatter(
                    x=chart["Year"],
                    y=pd.to_numeric(
                        chart[roe_col],
                        errors="coerce",
                    ),
                    mode="lines+markers",
                    name="ROE",
                )
            )

        if roce_col in chart.columns:
            fig.add_trace(
                go.Scatter(
                    x=chart["Year"],
                    y=pd.to_numeric(
                        chart[roce_col],
                        errors="coerce",
                    ),
                    mode="lines+markers",
                    name="ROCE",
                )
            )

        fig.update_layout(
            height=420,
            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20,
            ),
            xaxis_title="Year",
            yaxis_title="Percentage",
            hovermode="x unified",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:
        st.info(
            "ROE / ROCE history unavailable."
        )

else:
    st.info(
        "Ratio history is not available."
    )


# ---------------------------------------------------------------------
# Pros and Cons
# ---------------------------------------------------------------------

st.divider()

st.subheader("🧠 Pros & Cons")

if not pros_cons.empty:

    pros_column = find_column(
        pros_cons,
        [
            "pros",
            "pro",
            "positive",
            "advantages",
        ],
    )

    cons_column = find_column(
        pros_cons,
        [
            "cons",
            "con",
            "negative",
            "disadvantages",
        ],
    )

    pcol, ccol = st.columns(2)

    with pcol:
        st.markdown("### ✅ Pros")

        if pros_column:
            for value in pros_cons[pros_column].dropna():
                text = str(value).strip()

                if text:
                    st.success(text)

        else:
            st.info("No pros available.")

    with ccol:
        st.markdown("### ❌ Cons")

        if cons_column:
            for value in pros_cons[cons_column].dropna():
                text = str(value).strip()

                if text:
                    st.error(text)

        else:
            st.info("No cons available.")

else:
    st.info(
        "Pros and cons information is not available "
        "for this company."
    )


st.divider()

st.caption(
    f"Showing the latest available financial information for {ticker}. "
    "Missing values are displayed as N/A."
)