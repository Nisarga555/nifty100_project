import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_market_cap,
    get_ratios,
    get_sectors,
    get_pl,
    extract_year,
)


st.set_page_config(
    page_title="Sector Analysis | Nifty 100 Analytics",
    page_icon="🏭",
    layout="wide",
)


st.title("🏭 Sector Analysis")
st.caption(
    "Compare Nifty 100 companies across sectors and sub-sectors."
)


# ---------------------------------------------------------------------
# Load sources
# ---------------------------------------------------------------------

companies = get_companies()
sectors = get_sectors()
market_cap = get_market_cap()


if companies.empty or sectors.empty:
    st.error(
        "Company or sector data is unavailable."
    )
    st.stop()


# ---------------------------------------------------------------------
# Normalize master data
# ---------------------------------------------------------------------

master = companies.copy()

master["company_id"] = (
    master["id"]
    .astype(str)
    .str.strip()
    .str.upper()
)

sectors = sectors.copy()

sectors["company_id"] = (
    sectors["company_id"]
    .astype(str)
    .str.strip()
    .str.upper()
)


sector_master = sectors[
    [
        column
        for column in [
            "company_id",
            "broad_sector",
            "sub_sector",
        ]
        if column in sectors.columns
    ]
].drop_duplicates(
    "company_id",
    keep="first",
)


master = master.merge(
    sector_master,
    on="company_id",
    how="left",
)


# ---------------------------------------------------------------------
# Sector selector
# ---------------------------------------------------------------------

sector_list = sorted(
    master["broad_sector"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


if not sector_list:
    st.warning(
        "No sector assignments are available."
    )
    st.stop()


selected_sector = st.selectbox(
    "Select Sector",
    sector_list,
)


sector_companies = master[
    master["broad_sector"].astype(str)
    == selected_sector
].copy()


# ---------------------------------------------------------------------
# Collect latest available financial data
# ---------------------------------------------------------------------

rows = []


for _, company in sector_companies.iterrows():

    ticker = str(
        company["company_id"]
    ).strip().upper()

    ratios = get_ratios(ticker)

    if ratios.empty:
        continue

    ratios = ratios.copy()

    ratios["_year"] = ratios["year"].apply(
        extract_year
    )

    ratios = ratios.dropna(
        subset=["_year"]
    )

    if ratios.empty:
        continue

    ratios["_year"] = ratios["_year"].astype(int)

    latest = (
        ratios
        .sort_values("_year")
        .iloc[-1]
    )

    roe = pd.to_numeric(
        latest.get(
            "return_on_equity_pct",
            np.nan,
        ),
        errors="coerce",
    )

    rows.append(
        {
            "company_id": ticker,
            "company_name": company.get(
                "company_name",
                ticker,
            ),
            "sub_sector": company.get(
                "sub_sector",
                "Unknown",
            ),
            "roe": roe,
            "revenue": np.nan,
            "market_cap": np.nan,
        }
    )


analysis = pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Revenue from P&L
# ---------------------------------------------------------------------

if not analysis.empty:

    revenue_values = []

    for ticker in analysis[
        "company_id"
    ]:

        pl = get_pl(ticker)

        if pl.empty:
            revenue_values.append(np.nan)
            continue

        if "year" in pl.columns:
            pl = pl.copy()
            pl["_year"] = pl["year"].apply(
                extract_year
            )

            pl = pl.dropna(
                subset=["_year"]
            )

            if not pl.empty:
                pl["_year"] = pl[
                    "_year"
                ].astype(int)

                pl = pl.sort_values(
                    "_year"
                )

        if "sales" in pl.columns and not pl.empty:
            value = pd.to_numeric(
                pl.iloc[-1]["sales"],
                errors="coerce",
            )
        else:
            value = np.nan

        revenue_values.append(value)

    analysis["revenue"] = revenue_values


# ---------------------------------------------------------------------
# Market cap
# ---------------------------------------------------------------------

if not market_cap.empty:

    mc = market_cap.copy()

    if "company_id" in mc.columns:

        mc["company_id"] = (
            mc["company_id"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        if "year" in mc.columns:

            mc["_year"] = mc["year"].apply(
                extract_year
            )

            mc = mc.dropna(
                subset=["_year"]
            )

            if not mc.empty:
                mc["_year"] = mc[
                    "_year"
                ].astype(int)

                mc = (
                    mc
                    .sort_values("_year")
                    .drop_duplicates(
                        "company_id",
                        keep="last",
                    )
                )

        if "market_cap_crore" in mc.columns:

            mc_values = mc[
                [
                    "company_id",
                    "market_cap_crore",
                ]
            ].copy()

            mc_values[
                "market_cap_crore"
            ] = pd.to_numeric(
                mc_values[
                    "market_cap_crore"
                ],
                errors="coerce",
            )

            analysis = analysis.merge(
                mc_values.rename(
                    columns={
                        "market_cap_crore":
                        "market_cap"
                    }
                ),
                on="company_id",
                how="left",
                suffixes=(
                    "",
                    "_source",
                ),
            )

            if "market_cap_source" in analysis.columns:
                analysis["market_cap"] = (
                    analysis[
                        "market_cap_source"
                    ]
                    .fillna(
                        analysis["market_cap"]
                    )
                )

                analysis = analysis.drop(
                    columns=[
                        "market_cap_source"
                    ]
                )


# ---------------------------------------------------------------------
# Bubble chart
# ---------------------------------------------------------------------

st.subheader(
    f"📍 {selected_sector} — Company Map"
)


bubble = analysis.copy()

bubble["revenue"] = pd.to_numeric(
    bubble["revenue"],
    errors="coerce",
)

bubble["roe"] = pd.to_numeric(
    bubble["roe"],
    errors="coerce",
)

bubble["market_cap"] = pd.to_numeric(
    bubble["market_cap"],
    errors="coerce",
)


bubble = bubble.dropna(
    subset=[
        "revenue",
        "roe",
    ]
)


if bubble.empty:

    st.info(
        "Not enough revenue/ROE data is available "
        "to draw the sector bubble chart."
    )

else:

    # Prevent zero/negative bubble-size issues.
    bubble["bubble_size"] = (
        bubble["market_cap"]
        .abs()
        .fillna(1)
        .clip(lower=1)
    )

    fig = px.scatter(
        bubble,
        x="revenue",
        y="roe",
        size="bubble_size",
        color="sub_sector",
        hover_name="company_name",
        hover_data=[
            "company_id",
            "market_cap",
        ],
        size_max=55,
        title=(
            f"{selected_sector}: "
            "Revenue vs ROE"
        ),
    )

    fig.update_layout(
        height=600,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=30,
        ),
        xaxis_title="Revenue (₹ Cr)",
        yaxis_title="ROE (%)",
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )


# ---------------------------------------------------------------------
# Sector median KPI chart
# ---------------------------------------------------------------------

st.subheader(
    "📊 Sector Median KPIs"
)


sector_median = pd.DataFrame(
    {
        "Metric": [
            "ROE",
            "Revenue",
            "Market Cap",
        ],
        "Median": [
            analysis["roe"].median(),
            analysis["revenue"].median(),
            analysis["market_cap"].median(),
        ],
    }
)


sector_median["Median"] = pd.to_numeric(
    sector_median["Median"],
    errors="coerce",
)


sector_median = sector_median.dropna(
    subset=["Median"]
)


if not sector_median.empty:

    fig = px.bar(
        sector_median,
        x="Metric",
        y="Median",
        text_auto=".2f",
        title=(
            f"{selected_sector} — "
            "Median KPIs"
        ),
    )

    fig.update_layout(
        height=400,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=30,
        ),
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )
else:
    st.info(
        "Median KPI data unavailable."
    )