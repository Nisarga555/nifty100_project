import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_market_cap,
    get_ratios,
    get_sectors,
    extract_year,
)


st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="🏠",
    layout="wide",
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def clean_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def latest_row_for_year(dataframe, selected_year):
    """
    Return the latest available row for each company at or before
    the selected year.
    """
    if dataframe.empty or "year" not in dataframe.columns:
        return pd.DataFrame()

    data = dataframe.copy()
    data["_parsed_year"] = data["year"].apply(extract_year)

    data = data.dropna(subset=["_parsed_year"])
    data["_parsed_year"] = data["_parsed_year"].astype(int)

    data = data[data["_parsed_year"] <= selected_year]

    if data.empty:
        return data

    data = data.sort_values(
        ["company_id", "_parsed_year"],
        ascending=[True, False],
    )

    return data.drop_duplicates(
        subset=["company_id"],
        keep="first",
    )


@st.cache_data(ttl=600)
def build_home_dataset(selected_year):
    """Build the company-level dashboard snapshot."""

    companies = get_companies()
    sectors = get_sectors()
    market_cap = get_market_cap()

    if companies.empty:
        return pd.DataFrame()

    # -------------------------------------------------------------
    # Load all ratio history in one SQLite query for dashboard use.
    # -------------------------------------------------------------
    ratio_frames = []

    for ticker in companies["id"].dropna().astype(str):
        ratios = get_ratios(ticker)

        if not ratios.empty:
            ratio_frames.append(ratios)

    if ratio_frames:
        ratios_all = pd.concat(
            ratio_frames,
            ignore_index=True,
        )
    else:
        ratios_all = pd.DataFrame()

    latest_ratios = latest_row_for_year(
        ratios_all,
        selected_year,
    )

    # -------------------------------------------------------------
    # Company master
    # -------------------------------------------------------------
    master = companies.copy()

    master["company_id"] = master["id"].astype(str).str.strip().str.upper()

    # -------------------------------------------------------------
    # Sector information
    # -------------------------------------------------------------
    if not sectors.empty:
        sectors = sectors.copy()
        sectors["company_id"] = (
            sectors["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        sectors = sectors.drop_duplicates(
            "company_id",
            keep="first",
        )

        sector_cols = [
            column
            for column in [
                "company_id",
                "broad_sector",
                "sub_sector",
            ]
            if column in sectors.columns
        ]

        master = master.merge(
            sectors[sector_cols],
            on="company_id",
            how="left",
        )

    # -------------------------------------------------------------
    # Ratio data
    # -------------------------------------------------------------
    if not latest_ratios.empty:
        latest_ratios = latest_ratios.copy()

        latest_ratios["company_id"] = (
            latest_ratios["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        ratio_columns = [
            "company_id",
            "return_on_equity_pct",
            "debt_to_equity",
            "revenue_cagr_5yr",
            "composite_quality_score",
        ]

        ratio_columns = [
            column
            for column in ratio_columns
            if column in latest_ratios.columns
        ]

        master = master.merge(
            latest_ratios[ratio_columns],
            on="company_id",
            how="left",
        )

    # -------------------------------------------------------------
    # Market cap / valuation
    # -------------------------------------------------------------
    if not market_cap.empty and "company_id" in market_cap.columns:
        mc = market_cap.copy()

        mc["company_id"] = (
            mc["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        mc["_parsed_year"] = mc["year"].apply(extract_year)

        mc = mc.dropna(subset=["_parsed_year"])
        mc["_parsed_year"] = mc["_parsed_year"].astype(int)

        mc = mc[mc["_parsed_year"] <= selected_year]

        mc = mc.sort_values(
            ["company_id", "_parsed_year"],
            ascending=[True, False],
        )

        mc = mc.drop_duplicates(
            "company_id",
            keep="first",
        )

        valuation_columns = [
            "company_id",
            "pe_ratio",
        ]

        valuation_columns = [
            column
            for column in valuation_columns
            if column in mc.columns
        ]

        master = master.merge(
            mc[valuation_columns],
            on="company_id",
            how="left",
        )

    return master


# ---------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------

st.title("🏠 Nifty 100 Analytics")
st.caption(
    "Financial Intelligence Dashboard • "
    "92-company Nifty 100 universe"
)

companies = get_companies()

if companies.empty:
    st.error(
        "Company data could not be loaded. "
        "Please check data/raw/companies.xlsx."
    )
    st.stop()


# ---------------------------------------------------------------------
# Year selector
# ---------------------------------------------------------------------

st.sidebar.header("Dashboard Controls")

selected_year = st.sidebar.selectbox(
    "Analysis Year",
    list(range(2024, 2018, -1)),
    index=0,
)

data = build_home_dataset(selected_year)

if data.empty:
    st.warning(
        f"No dashboard data is available up to {selected_year}."
    )
    st.stop()


# ---------------------------------------------------------------------
# KPI calculations
# ---------------------------------------------------------------------

roe = (
    clean_numeric(data["return_on_equity_pct"])
    if "return_on_equity_pct" in data.columns
    else pd.Series(dtype=float)
)

de = (
    clean_numeric(data["debt_to_equity"])
    if "debt_to_equity" in data.columns
    else pd.Series(dtype=float)
)

pe = (
    clean_numeric(data["pe_ratio"])
    if "pe_ratio" in data.columns
    else pd.Series(dtype=float)
)

revenue_cagr = (
    clean_numeric(data["revenue_cagr_5yr"])
    if "revenue_cagr_5yr" in data.columns
    else pd.Series(dtype=float)
)

average_roe = roe.mean()
median_pe = pe.median()
median_de = de.median()
median_revenue_cagr = revenue_cagr.median()

debt_free_count = int(
    (de.fillna(np.nan) == 0).sum()
)


# ---------------------------------------------------------------------
# Six KPI tiles
# ---------------------------------------------------------------------

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.metric(
        "Average ROE",
        f"{average_roe:.2f}%"
        if pd.notna(average_roe)
        else "N/A",
    )

with k2:
    st.metric(
        "Median P/E",
        f"{median_pe:.2f}"
        if pd.notna(median_pe)
        else "N/A",
    )

with k3:
    st.metric(
        "Median D/E",
        f"{median_de:.2f}"
        if pd.notna(median_de)
        else "N/A",
    )

with k4:
    st.metric(
        "Total Companies",
        f"{len(data):,}",
    )

with k5:
    st.metric(
        "Median Revenue CAGR 5Y",
        f"{median_revenue_cagr:.2f}%"
        if pd.notna(median_revenue_cagr)
        else "N/A",
    )

with k6:
    st.metric(
        "Debt-Free Companies",
        f"{debt_free_count}",
    )


st.divider()


# ---------------------------------------------------------------------
# Sector breakdown + top companies
# ---------------------------------------------------------------------

left, right = st.columns([1, 1.4])


with left:
    st.subheader("🏭 Sector Breakdown")

    if "broad_sector" in data.columns:
        sector_counts = (
            data["broad_sector"]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
        )

        sector_counts.columns = [
            "Sector",
            "Companies",
        ]

        fig = px.pie(
            sector_counts,
            names="Sector",
            values="Companies",
            hole=0.55,
            title=f"Companies by Sector — {selected_year}",
        )

        fig.update_layout(
            margin=dict(l=10, r=10, t=50, b=10),
            height=430,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.25,
            ),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    else:
        st.info("Sector data unavailable.")


with right:
    st.subheader("🏆 Top 5 Companies by Composite Quality")

    if "composite_quality_score" in data.columns:
        top5 = data.copy()

        top5["composite_quality_score"] = clean_numeric(
            top5["composite_quality_score"]
        )

        top5 = top5.sort_values(
            "composite_quality_score",
            ascending=False,
        ).head(5)

        display_columns = []

        for column in [
            "company_id",
            "company_name",
            "broad_sector",
            "composite_quality_score",
        ]:
            if column in top5.columns:
                display_columns.append(column)

        table = top5[display_columns].copy()

        rename_map = {
            "company_id": "Ticker",
            "company_name": "Company",
            "broad_sector": "Sector",
            "composite_quality_score": "Quality Score",
        }

        table = table.rename(
            columns=rename_map
        )

        if "Quality Score" in table.columns:
            table["Quality Score"] = table[
                "Quality Score"
            ].round(2)

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("Composite quality scores unavailable.")


# ---------------------------------------------------------------------
# Data availability note
# ---------------------------------------------------------------------

st.divider()

st.caption(
    f"Dashboard snapshot: data available through {selected_year}. "
    "Missing financial values are excluded from individual KPI calculations."
)