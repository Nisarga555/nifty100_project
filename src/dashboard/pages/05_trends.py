import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    extract_year,
    get_companies,
    get_ratios,
)

st.set_page_config(
    page_title="Trend Analysis | Nifty 100 Analytics",
    page_icon="📈",
    layout="wide",
)


st.title("📈 Trend Analysis")
st.caption("Explore up to 10 years of financial and operating trends.")


# ---------------------------------------------------------------------
# Company search
# ---------------------------------------------------------------------

companies = get_companies()

if companies.empty:
    st.error("Company data is unavailable.")
    st.stop()


companies = companies.copy()

companies["ticker"] = companies["id"].astype(str).str.strip().str.upper()

companies["company_name"] = companies["company_name"].fillna("").astype(str)

companies["label"] = companies["ticker"] + " — " + companies["company_name"]


search = st.text_input(
    "🔎 Search company or ticker",
    placeholder="Type TCS, INFY, RELIANCE, etc.",
)


if search.strip():
    q = search.strip().lower()

    matches = companies[
        companies["ticker"].str.lower().str.contains(q, na=False)
        | companies["company_name"].str.lower().str.contains(q, na=False)
    ]
else:
    matches = companies


if matches.empty:
    st.warning("Ticker not found — please try another")
    st.stop()


selected_label = st.selectbox(
    "Select company",
    matches["label"].head(20).tolist(),
)

ticker = selected_label.split(" — ")[0]


# ---------------------------------------------------------------------
# Load ratio history
# ---------------------------------------------------------------------

ratios = get_ratios(ticker)

if ratios.empty:
    st.warning(f"No financial history is available for {ticker}.")
    st.stop()


ratios = ratios.copy()

ratios["_year"] = ratios["year"].apply(extract_year)

ratios = ratios.dropna(subset=["_year"])

ratios["_year"] = ratios["_year"].astype(int)

ratios = (
    ratios.sort_values("_year")
    .drop_duplicates(
        "_year",
        keep="last",
    )
    .tail(10)
)


# ---------------------------------------------------------------------
# Metric mapping
# ---------------------------------------------------------------------

METRICS = {
    "ROE (%)": "return_on_equity_pct",
    "ROCE (%)": "return_on_capital_employed_pct",
    "Net Profit Margin (%)": "net_profit_margin_pct",
    "Operating Profit Margin (%)": "operating_profit_margin_pct",
    "Debt / Equity": "debt_to_equity",
    "Interest Coverage": "interest_coverage",
    "Asset Turnover": "asset_turnover",
    "FCF (₹ Cr)": "free_cash_flow_cr",
    "Revenue CAGR 5Y (%)": "revenue_cagr_5yr",
    "PAT CAGR 5Y (%)": "pat_cagr_5yr",
}


available_metrics = [
    name for name, column in METRICS.items() if column in ratios.columns
]


if not available_metrics:
    st.warning("No trend metrics are available for this company.")
    st.stop()


# ---------------------------------------------------------------------
# Metric selector
# ---------------------------------------------------------------------

selected_metrics = st.multiselect(
    "Select up to 3 metrics",
    options=available_metrics,
    default=available_metrics[:2],
    max_selections=3,
)


if not selected_metrics:
    st.info("Select at least one metric to display the trend.")
    st.stop()


# ---------------------------------------------------------------------
# Build chart
# ---------------------------------------------------------------------

fig = go.Figure()


for metric_name in selected_metrics:

    column = METRICS[metric_name]

    values = pd.to_numeric(
        ratios[column],
        errors="coerce",
    )

    fig.add_trace(
        go.Scatter(
            x=ratios["_year"],
            y=values,
            mode="lines+markers",
            name=metric_name,
            connectgaps=False,
        )
    )


fig.update_layout(
    title=f"{ticker} — 10 Year Trend",
    height=560,
    hovermode="x unified",
    margin=dict(
        l=30,
        r=30,
        t=60,
        b=30,
    ),
    xaxis_title="Year",
    yaxis_title="Value",
    legend_title="Metric",
)


st.plotly_chart(
    fig,
    width="stretch",
)


# ---------------------------------------------------------------------
# YoY change table / annotation
# ---------------------------------------------------------------------

st.subheader("📊 Year-over-Year Change")

yoy = pd.DataFrame()

for metric_name in selected_metrics:

    column = METRICS[metric_name]

    values = pd.to_numeric(
        ratios[column],
        errors="coerce",
    )

    yoy_values = values.pct_change() * 100

    yoy[metric_name] = yoy_values.round(2)


yoy.insert(
    0,
    "Year",
    ratios["_year"].values,
)

st.dataframe(
    yoy,
    width="stretch",
    hide_index=True,
)

st.caption(
    "YoY values represent percentage change from the previous "
    "available year. N/A indicates insufficient or missing data."
)
