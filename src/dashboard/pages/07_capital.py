import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils.db import (
    get_companies,
    get_ratios,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Capital Allocation | Nifty 100 Analytics",
    page_icon="💰",
    layout="wide",
)


# ============================================================
# TITLE
# ============================================================

st.title("💰 Capital Allocation")
st.caption(
    "Nifty 100 companies grouped by their latest capital allocation pattern."
)


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=600)
def load_capital_data():

    companies = get_companies()
    ratios = []

    # Load ratio history for every company
    for _, company in companies.iterrows():

        company_id = str(
            company["id"]
        ).strip()

        try:
            data = get_ratios(
                company_id
            )

            if data is not None and not data.empty:

                data = data.copy()

                data["company_id"] = (
                    company_id
                )

                ratios.append(data)

        except Exception:
            continue

    if not ratios:
        return pd.DataFrame()

    ratios = pd.concat(
        ratios,
        ignore_index=True,
    )

    # --------------------------------------------------------
    # Company names
    # --------------------------------------------------------

    company_names = companies[
        [
            "id",
            "company_name",
        ]
    ].copy()

    company_names = company_names.rename(
        columns={
            "id": "company_id"
        }
    )

    company_names["company_id"] = (
        company_names["company_id"]
        .astype(str)
        .str.strip()
    )

    ratios["company_id"] = (
        ratios["company_id"]
        .astype(str)
        .str.strip()
    )

    ratios = ratios.merge(
        company_names,
        on="company_id",
        how="left",
    )

    # --------------------------------------------------------
    # Year
    # --------------------------------------------------------

    if "year" in ratios.columns:

        ratios["year_num"] = (
            ratios["year"]
            .astype(str)
            .str.extract(
                r"(\d{4})",
                expand=False,
            )
        )

        ratios["year_num"] = pd.to_numeric(
            ratios["year_num"],
            errors="coerce",
        )

    else:

        ratios["year_num"] = 0

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    numeric_columns = [
        "free_cash_flow_cr",
        "capex_cr",
        "cash_from_operations_cr",
        "net_profit_cr",
        "dividend_payout_ratio_pct",
        "total_debt_cr",
    ]

    for column in numeric_columns:

        if column in ratios.columns:

            ratios[column] = pd.to_numeric(
                ratios[column],
                errors="coerce",
            )

    # ========================================================
    # LATEST AVAILABLE ROW PER COMPANY
    # ========================================================

    ratios = ratios.sort_values(
        [
            "company_id",
            "year_num",
        ],
        ascending=[
            True,
            False,
        ],
    )

    latest = (
        ratios
        .drop_duplicates(
            "company_id",
            keep="first",
        )
        .copy()
    )

    # ========================================================
    # CAPITAL ALLOCATION CLASSIFICATION
    # ========================================================

    latest["capital_allocation_pattern"] = (
        latest.apply(
            classify_capital_allocation,
            axis=1,
        )
    )

    return latest


# ============================================================
# CAPITAL ALLOCATION CLASSIFIER
# ============================================================

def classify_capital_allocation(row):
    """
    Classify a company into one of eight capital allocation
    patterns using the latest available financial information.
    """

    fcf = row.get(
        "free_cash_flow_cr",
        None,
    )

    capex = row.get(
        "capex_cr",
        None,
    )

    cfo = row.get(
        "cash_from_operations_cr",
        None,
    )

    dividend = row.get(
        "dividend_payout_ratio_pct",
        None,
    )

    debt = row.get(
        "total_debt_cr",
        None,
    )

    # Convert safely
    values = [
        fcf,
        capex,
        cfo,
        dividend,
        debt,
    ]

    values = [
        pd.to_numeric(
            value,
            errors="coerce",
        )
        for value in values
    ]

    fcf, capex, cfo, dividend, debt = values

    # --------------------------------------------------------
    # Missing data
    # --------------------------------------------------------

    if pd.isna(fcf) and pd.isna(cfo):

        return "Insufficient Data"

    # --------------------------------------------------------
    # Helpful boolean indicators
    # --------------------------------------------------------

    positive_fcf = (
        pd.notna(fcf)
        and fcf > 0
    )

    negative_fcf = (
        pd.notna(fcf)
        and fcf < 0
    )

    positive_cfo = (
        pd.notna(cfo)
        and cfo > 0
    )

    high_capex = (
        pd.notna(capex)
        and pd.notna(cfo)
        and capex > 0.5 * abs(cfo)
    )

    high_dividend = (
        pd.notna(dividend)
        and dividend >= 50
    )

    low_dividend = (
        pd.notna(dividend)
        and dividend < 20
    )

    has_debt = (
        pd.notna(debt)
        and debt > 0
    )

    # ========================================================
    # 8 PATTERNS
    # ========================================================

    # 1. Strong Cash Generator
    if (
        positive_fcf
        and positive_cfo
        and not high_capex
        and (
            pd.isna(dividend)
            or dividend < 50
        )
    ):
        return "Strong Cash Generator"

    # 2. Growth Reinvestment
    if (
        positive_cfo
        and high_capex
        and positive_fcf
    ):
        return "Growth Reinvestment"

    # 3. High Dividend Payer
    if (
        positive_fcf
        and high_dividend
    ):
        return "High Dividend Payer"

    # 4. Conservative Capital Allocation
    if (
        positive_fcf
        and positive_cfo
        and low_dividend
        and not high_capex
        and not has_debt
    ):
        return "Conservative Capital Allocation"

    # 5. Debt-Funded Expansion
    if (
        high_capex
        and has_debt
    ):
        return "Debt-Funded Expansion"

    # 6. Cash Burn / Investment Phase
    if (
        negative_fcf
        and positive_cfo
        and high_capex
    ):
        return "Cash Burn / Investment Phase"

    # 7. Weak Cash Conversion
    if (
        pd.notna(cfo)
        and pd.notna(fcf)
        and cfo > 0
        and fcf < 0
    ):
        return "Weak Cash Conversion"

    # 8. Capital Stress
    if (
        (
            negative_fcf
            and negative_fcf
        )
        or (
            pd.notna(cfo)
            and cfo < 0
        )
    ):
        return "Capital Stress"

    # Fallback
    return "Other"


# ============================================================
# MAIN DATASET
# ============================================================

try:

    data = load_capital_data()

except Exception as e:

    st.error(
        f"Unable to load capital allocation data: {e}"
    )

    st.stop()


if data.empty:

    st.warning(
        "Capital allocation data is currently unavailable."
    )

    st.stop()


# ============================================================
# SUMMARY METRICS
# ============================================================

st.subheader("Capital Allocation Overview")

total_companies = (
    data["company_id"]
    .nunique()
)

total_patterns = (
    data[
        "capital_allocation_pattern"
    ]
    .nunique()
)

largest_pattern = (
    data[
        "capital_allocation_pattern"
    ]
    .value_counts()
    .idxmax()
)

largest_pattern_count = (
    data[
        "capital_allocation_pattern"
    ]
    .value_counts()
    .max()
)


col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Companies",
        total_companies,
    )

with col2:

    st.metric(
        "Patterns",
        total_patterns,
    )

with col3:

    st.metric(
        "Largest Pattern",
        largest_pattern,
    )

with col4:

    st.metric(
        "Companies",
        largest_pattern_count,
    )


# ============================================================
# PATTERN COUNTS
# ============================================================

pattern_counts = (
    data[
        "capital_allocation_pattern"
    ]
    .value_counts()
    .reset_index()
)

pattern_counts.columns = [
    "Pattern",
    "Companies",
]


# ============================================================
# TREEMAP
# ============================================================

st.subheader(
    "Capital Allocation Pattern Map"
)

fig = px.treemap(
    pattern_counts,
    path=[
        "Pattern"
    ],
    values="Companies",
)

fig.update_layout(
    margin=dict(
        t=30,
        l=10,
        r=10,
        b=10,
    ),
)

st.plotly_chart(
    fig,
    width="stretch",
)


# ============================================================
# PATTERN DETAILS
# ============================================================

st.subheader(
    "Explore Companies by Pattern"
)

patterns = sorted(
    data[
        "capital_allocation_pattern"
    ]
    .dropna()
    .unique()
    .tolist()
)

selected_pattern = st.selectbox(
    "Select a capital allocation pattern",
    patterns,
)


# ============================================================
# FILTER COMPANY DATA
# ============================================================

selected_companies = data[
    data[
        "capital_allocation_pattern"
    ]
    == selected_pattern
].copy()


st.write(
    f"### {selected_pattern}"
)

st.write(
    f"{len(selected_companies)} companies belong to this pattern."
)


# ============================================================
# COMPANY LIST
# ============================================================

display_columns = [
    "company_id",
    "company_name",
    "year",
    "free_cash_flow_cr",
    "capex_cr",
    "cash_from_operations_cr",
    "dividend_payout_ratio_pct",
    "total_debt_cr",
]


available_columns = [
    column
    for column in display_columns
    if column in selected_companies.columns
]


company_table = selected_companies[
    available_columns
].copy()


# ============================================================
# FORMATTING
# ============================================================

rename_columns = {
    "company_id": "Company ID",
    "company_name": "Company",
    "year": "Year",
    "free_cash_flow_cr": "FCF (₹ Cr)",
    "capex_cr": "CapEx (₹ Cr)",
    "cash_from_operations_cr": "CFO (₹ Cr)",
    "dividend_payout_ratio_pct": "Dividend Payout %",
    "total_debt_cr": "Total Debt (₹ Cr)",
}

company_table = company_table.rename(
    columns=rename_columns
)


# ============================================================
# DISPLAY TABLE
# ============================================================

st.dataframe(
    company_table,
    width="stretch",
    hide_index=True,
)


# ============================================================
# DOWNLOAD
# ============================================================

csv_data = company_table.to_csv(
    index=False
)

st.download_button(
    label="⬇️ Download Company List",
    data=csv_data,
    file_name="capital_allocation_companies.csv",
    mime="text/csv",
)