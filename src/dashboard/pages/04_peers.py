import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    get_all_peer_groups,
    get_companies,
    get_peer_percentiles,
    get_peers,
    get_ratios,
)

st.set_page_config(
    page_title="Peer Comparison | Nifty 100 Analytics",
    page_icon="👥",
    layout="wide",
)


st.title("👥 Peer Comparison")
st.caption(
    "Compare companies against their peer-group benchmark "
    "using percentile-ranked financial metrics."
)


# ---------------------------------------------------------------------
# Peer groups
# ---------------------------------------------------------------------

peer_groups = get_all_peer_groups()

if not peer_groups:
    st.error("No peer groups are available.")
    st.stop()


selected_group = st.selectbox(
    "Select Peer Group",
    peer_groups,
)


# ---------------------------------------------------------------------
# Peer companies
# ---------------------------------------------------------------------

peer_assignments = get_peers(selected_group)

companies = get_companies()

if peer_assignments.empty:
    st.warning("No companies are assigned to this peer group.")
    st.stop()


# Normalize IDs
peer_assignments = peer_assignments.copy()

peer_assignments["company_id"] = (
    peer_assignments["company_id"].astype(str).str.strip().str.upper()
)

companies = companies.copy()

companies["company_id"] = companies["id"].astype(str).str.strip().str.upper()


peer_assignments = peer_assignments.merge(
    companies[
        [
            "company_id",
            "company_name",
        ]
    ],
    on="company_id",
    how="left",
)


# ---------------------------------------------------------------------
# Select company
# ---------------------------------------------------------------------

company_options = peer_assignments[
    [
        "company_id",
        "company_name",
    ]
].copy()

company_options["label"] = (
    company_options["company_id"] + " — " + company_options["company_name"].fillna("")
)


selected_label = st.selectbox(
    "Select company",
    company_options["label"].tolist(),
)


selected_ticker = selected_label.split(" — ")[0].strip().upper()


# ---------------------------------------------------------------------
# Percentile data
# ---------------------------------------------------------------------

percentiles = get_peer_percentiles(peer_group_name=selected_group)

if percentiles.empty:
    st.error("Peer percentile data is unavailable for this group.")
    st.stop()


# ---------------------------------------------------------------------
# Latest ratio row for selected company
# ---------------------------------------------------------------------

ratios = get_ratios(selected_ticker)

if ratios.empty:
    st.warning("Financial ratio history is unavailable for " f"{selected_ticker}.")
    st.stop()


ratios = ratios.copy()

ratios["_year_numeric"] = pd.to_numeric(
    ratios["year"].astype(str).str.extract(r"(\d{4})")[0],
    errors="coerce",
)

ratios = ratios.sort_values("_year_numeric")

latest_ratio = ratios.iloc[-1]


# ---------------------------------------------------------------------
# Radar metrics
# ---------------------------------------------------------------------

radar_metrics = [
    ("ROE", "roe"),
    ("ROCE", "roce"),
    ("NPM", "npm"),
    ("D/E", "de"),
    ("FCF Score", "fcf"),
    ("PAT CAGR 5Y", "pat_cagr_5yr"),
    ("Revenue CAGR 5Y", "revenue_cagr_5yr"),
    ("Composite Score", "composite"),
]


# Peer percentile values
selected_pct = percentiles[
    percentiles["company_id"].astype(str).str.upper() == selected_ticker
].copy()


# We use percentile rank for the first seven metrics.
# Composite score is taken directly from financial_ratios.

selected_values = []

peer_average_values = []


for label, metric in radar_metrics:

    if metric == "composite":

        value = pd.to_numeric(
            latest_ratio.get(
                "composite_quality_score",
                np.nan,
            ),
            errors="coerce",
        )

        # Compare composite against peer group average.
        all_peer_ratios = []

        for ticker in peer_assignments["company_id"].dropna().unique():

            company_ratio = get_ratios(ticker)

            if company_ratio.empty:
                continue

            company_ratio = company_ratio.copy()

            company_ratio["_year_numeric"] = pd.to_numeric(
                company_ratio["year"].astype(str).str.extract(r"(\d{4})")[0],
                errors="coerce",
            )

            company_ratio = company_ratio.sort_values("_year_numeric")

            val = pd.to_numeric(
                company_ratio.iloc[-1].get(
                    "composite_quality_score",
                    np.nan,
                ),
                errors="coerce",
            )

            if pd.notna(val):
                all_peer_ratios.append(val)

        peer_avg = np.mean(all_peer_ratios) if all_peer_ratios else np.nan

    else:

        row = selected_pct[selected_pct["metric"] == metric]

        value = (
            float(row.iloc[0]["percentile_rank"])
            if not row.empty and pd.notna(row.iloc[0]["percentile_rank"])
            else np.nan
        )

        group_rows = percentiles[percentiles["metric"] == metric]

        peer_avg = pd.to_numeric(
            group_rows["percentile_rank"],
            errors="coerce",
        ).mean()

    selected_values.append(value)
    peer_average_values.append(peer_avg)


# ---------------------------------------------------------------------
# Radar chart
# ---------------------------------------------------------------------

st.subheader(f"📡 {selected_ticker} vs {selected_group} Average")


radar_labels = [item[0] for item in radar_metrics]


# Normalize composite to percentile-style scale for radar.
composite_index = 7

if pd.notna(selected_values[composite_index]):

    peer_composite = peer_average_values[composite_index]

    # Keep composite directly on 0-100 scale.
    selected_values[composite_index] = max(
        0,
        min(
            100,
            float(selected_values[composite_index]),
        ),
    )

    peer_average_values[composite_index] = (
        max(
            0,
            min(
                100,
                float(peer_composite),
            ),
        )
        if pd.notna(peer_composite)
        else 0
    )


radar_company = selected_values + [selected_values[0]]

radar_average = peer_average_values + [peer_average_values[0]]

radar_axis = radar_labels + [radar_labels[0]]


fig = go.Figure()


fig.add_trace(
    go.Scatterpolar(
        r=radar_company,
        theta=radar_axis,
        fill="toself",
        name=selected_ticker,
    )
)


fig.add_trace(
    go.Scatterpolar(
        r=radar_average,
        theta=radar_axis,
        fill=None,
        mode="lines",
        name="Peer Average",
    )
)


fig.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 100],
        )
    ),
    height=600,
    margin=dict(
        l=40,
        r=40,
        t=50,
        b=40,
    ),
)


st.plotly_chart(
    fig,
    use_container_width=True,
)


st.caption(
    "Radar values are percentile-style scores (0–100). "
    "Higher is better; D/E is inverse-ranked."
)


# ---------------------------------------------------------------------
# Peer company table
# ---------------------------------------------------------------------

st.divider()

st.subheader(f"📋 Companies in {selected_group}")


group_table = percentiles.copy()

group_table["company_id"] = (
    group_table["company_id"].astype(str).str.strip().str.upper()
)


# Pivot percentile data
pivot = group_table.pivot_table(
    index="company_id",
    columns="metric",
    values="percentile_rank",
    aggfunc="first",
).reset_index()


# Add names
pivot = pivot.merge(
    company_options[
        [
            "company_id",
            "company_name",
        ]
    ],
    on="company_id",
    how="left",
)


# Benchmark
if "is_benchmark" in peer_assignments.columns:
    benchmark_ids = set(
        peer_assignments.loc[
            peer_assignments["is_benchmark"]
            .astype(str)
            .str.lower()
            .isin(
                [
                    "true",
                    "1",
                    "yes",
                ]
            ),
            "company_id",
        ]
    )
else:
    benchmark_ids = set()


pivot["Benchmark"] = pivot["company_id"].isin(benchmark_ids)


# Put benchmark first
pivot = pivot.sort_values(
    "Benchmark",
    ascending=False,
)


# Rename columns
metric_names = {
    "roe": "ROE %ile",
    "roce": "ROCE %ile",
    "npm": "NPM %ile",
    "de": "D/E %ile",
    "fcf": "FCF %ile",
    "pat_cagr_5yr": "PAT CAGR %ile",
    "revenue_cagr_5yr": "Revenue CAGR %ile",
    "eps_cagr_5yr": "EPS CAGR %ile",
    "icr": "ICR %ile",
    "asset_turnover": "Asset Turnover %ile",
}

pivot = pivot.rename(columns=metric_names)


ordered = [
    "company_id",
    "company_name",
]

for column in metric_names.values():
    if column in pivot.columns:
        ordered.append(column)

ordered.append("Benchmark")

ordered = [column for column in ordered if column in pivot.columns]


table = pivot[ordered].copy()


for column in table.select_dtypes(include="number").columns:
    table[column] = table[column].round(1)


def highlight_benchmark(row):
    if row.get("Benchmark", False):
        return ["font-weight: bold" for _ in row]

    return ["" for _ in row]


st.dataframe(
    table.style.apply(
        highlight_benchmark,
        axis=1,
    ),
    use_container_width=True,
    hide_index=True,
)


st.caption(
    f"{len(peer_assignments)} companies assigned to "
    f"the {selected_group} peer group."
)
