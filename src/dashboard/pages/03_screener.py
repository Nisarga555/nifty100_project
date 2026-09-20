import numpy as np
import pandas as pd
import streamlit as st

from src.screener.engine import (
    build_screener_dataset,
    load_config,
    load_ratio_data,
    load_supporting_data,
)

st.set_page_config(
    page_title="Screener | Nifty 100 Analytics",
    page_icon="🔎",
    layout="wide",
)


st.title("🔎 Nifty 100 Stock Screener")
st.caption(
    "Apply financial quality, valuation, growth and leverage filters "
    "to the 92-company universe."
)


# ---------------------------------------------------------------------
# Load engine data
# ---------------------------------------------------------------------


@st.cache_data(ttl=600)
def load_screener_data():
    config = load_config()
    ratios = load_ratio_data()
    supporting = load_supporting_data()

    dataset = build_screener_dataset(
        ratios,
        supporting,
    )

    return config, dataset


try:
    config, dataset = load_screener_data()
except Exception as exc:
    st.error(f"Unable to load screener data: {exc}")
    st.stop()


if dataset.empty:
    st.warning("No screener data available.")
    st.stop()


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def apply_custom_filters(data):
    """Apply the ten visible screener filters."""

    result = data.copy()

    def numeric_filter(column, threshold, operator):
        nonlocal result

        if column not in result.columns:
            return

        values = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        if operator == ">=":
            mask = values >= threshold
        elif operator == "<=":
            mask = values <= threshold
        else:
            mask = pd.Series(True, index=result.index)

        # Missing values fail a user-selected filter.
        result = result.loc[mask.fillna(False)]

    numeric_filter(
        "return_on_equity_pct",
        st.session_state.roe_min,
        ">=",
    )

    # -------------------------------------------------------------
    # D/E — Financials are exempt.
    # -------------------------------------------------------------
    if "debt_to_equity" in result.columns:

        de = pd.to_numeric(
            result["debt_to_equity"],
            errors="coerce",
        )

        financials = (
            result["broad_sector"].astype(str).str.strip().str.lower().eq("financials")
            if "broad_sector" in result.columns
            else pd.Series(
                False,
                index=result.index,
            )
        )

        de_mask = financials | de.le(st.session_state.de_max).fillna(False)

        result = result.loc[de_mask]

    numeric_filter(
        "free_cash_flow",
        st.session_state.fcf_min,
        ">=",
    )

    numeric_filter(
        "revenue_cagr_5yr",
        st.session_state.revenue_cagr_min,
        ">=",
    )

    numeric_filter(
        "pat_cagr_5yr",
        st.session_state.pat_cagr_min,
        ">=",
    )

    numeric_filter(
        "operating_profit_margin_pct",
        st.session_state.opm_min,
        ">=",
    )

    numeric_filter(
        "pe_ratio",
        st.session_state.pe_max,
        "<=",
    )

    numeric_filter(
        "pb_ratio",
        st.session_state.pb_max,
        "<=",
    )

    numeric_filter(
        "dividend_yield_pct",
        st.session_state.dividend_yield_min,
        ">=",
    )

    # -------------------------------------------------------------
    # ICR — Debt Free = infinity.
    # -------------------------------------------------------------
    if "interest_coverage" in result.columns:

        icr = pd.to_numeric(
            result["interest_coverage"],
            errors="coerce",
        )

        if "icr_label" in result.columns:
            debt_free = (
                result["icr_label"].astype(str).str.strip().str.lower().eq("debt free")
            )
        else:
            debt_free = pd.Series(
                False,
                index=result.index,
            )

        icr_mask = debt_free | icr.ge(st.session_state.icr_min).fillna(False)

        result = result.loc[icr_mask]

    return result


def get_value(dataframe, column, default=np.nan):
    if column not in dataframe.columns:
        return pd.Series(
            default,
            index=dataframe.index,
        )

    return pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )


# ---------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------

PRESETS = {
    "Custom": {},
    "Quality Compounder": {
        "roe_min": 12.0,
        "de_max": 1.0,
        "fcf_min": 0.0,
        "revenue_cagr_min": 10.0,
    },
    "Value Pick": {
        "de_max": 2.0,
        "pe_max": 30.0,
        "pb_max": 5.0,
        "dividend_yield_min": 1.5,
    },
    "Growth Accelerator": {
        "de_max": 2.0,
        "revenue_cagr_min": 15.0,
        "pat_cagr_min": 20.0,
    },
    "Dividend Champion": {
        "fcf_min": 0.0,
        "dividend_yield_min": 1.5,
    },
    "Debt-Free Blue Chip": {
        "roe_min": 12.0,
        "de_max": 0.0,
    },
    "Turnaround Watch": {
        "revenue_cagr_min": 10.0,
    },
}


def set_preset(name):
    values = PRESETS[name]

    defaults = {
        "roe_min": 0.0,
        "de_max": 20.0,
        "fcf_min": -100000.0,
        "revenue_cagr_min": -100.0,
        "pat_cagr_min": -100.0,
        "opm_min": -100.0,
        "pe_max": 200.0,
        "pb_max": 100.0,
        "dividend_yield_min": 0.0,
        "icr_min": 0.0,
    }

    for key, default in defaults.items():
        st.session_state[key] = values.get(
            key,
            default,
        )


# ---------------------------------------------------------------------
# Initialize state
# ---------------------------------------------------------------------

defaults = {
    "roe_min": 0.0,
    "de_max": 20.0,
    "fcf_min": -100000.0,
    "revenue_cagr_min": -100.0,
    "pat_cagr_min": -100.0,
    "opm_min": -100.0,
    "pe_max": 200.0,
    "pb_max": 100.0,
    "dividend_yield_min": 0.0,
    "icr_min": 0.0,
    "preset_name": "Custom",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

st.sidebar.header("🎛️ Screener Filters")

st.sidebar.selectbox(
    "Preset",
    list(PRESETS.keys()),
    key="preset_name",
    on_change=lambda: set_preset(st.session_state.preset_name),
)


st.sidebar.markdown("---")
st.sidebar.subheader("Financial Filters")


st.sidebar.slider(
    "ROE minimum (%)",
    min_value=-100.0,
    max_value=100.0,
    step=1.0,
    key="roe_min",
)

st.sidebar.slider(
    "D/E maximum",
    min_value=0.0,
    max_value=20.0,
    step=0.1,
    key="de_max",
)

st.sidebar.slider(
    "FCF minimum (₹ Cr)",
    min_value=-100000.0,
    max_value=100000.0,
    step=100.0,
    key="fcf_min",
)

st.sidebar.slider(
    "Revenue CAGR 5Y minimum (%)",
    min_value=-100.0,
    max_value=100.0,
    step=1.0,
    key="revenue_cagr_min",
)

st.sidebar.slider(
    "PAT CAGR 5Y minimum (%)",
    min_value=-100.0,
    max_value=100.0,
    step=1.0,
    key="pat_cagr_min",
)

st.sidebar.slider(
    "OPM minimum (%)",
    min_value=-100.0,
    max_value=100.0,
    step=1.0,
    key="opm_min",
)

st.sidebar.slider(
    "P/E maximum",
    min_value=0.0,
    max_value=200.0,
    step=1.0,
    key="pe_max",
)

st.sidebar.slider(
    "P/B maximum",
    min_value=0.0,
    max_value=100.0,
    step=1.0,
    key="pb_max",
)

st.sidebar.slider(
    "Dividend Yield minimum (%)",
    min_value=0.0,
    max_value=20.0,
    step=0.5,
    key="dividend_yield_min",
)

st.sidebar.slider(
    "ICR minimum",
    min_value=0.0,
    max_value=50.0,
    step=0.5,
    key="icr_min",
)


# ---------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------

filtered = apply_custom_filters(dataset)


# Composite score first
if "composite_quality_score" in filtered.columns:
    filtered = filtered.sort_values(
        "composite_quality_score",
        ascending=False,
    )


# ---------------------------------------------------------------------
# Result count
# ---------------------------------------------------------------------

st.subheader(f"{len(filtered)} companies match your filters")


# ---------------------------------------------------------------------
# Visible result table
# ---------------------------------------------------------------------

display_columns = [
    "company_id",
    "company_name",
    "broad_sector",
    "composite_quality_score",
    "return_on_equity_pct",
    "debt_to_equity",
    "free_cash_flow",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "operating_profit_margin_pct",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
    "interest_coverage",
]


display_columns = [column for column in display_columns if column in filtered.columns]


visible = filtered[display_columns].copy()


rename_columns = {
    "company_id": "Ticker",
    "company_name": "Company",
    "broad_sector": "Sector",
    "composite_quality_score": "Composite Score",
    "return_on_equity_pct": "ROE %",
    "debt_to_equity": "D/E",
    "free_cash_flow": "FCF ₹Cr",
    "revenue_cagr_5yr": "Revenue CAGR 5Y %",
    "pat_cagr_5yr": "PAT CAGR 5Y %",
    "operating_profit_margin_pct": "OPM %",
    "pe_ratio": "P/E",
    "pb_ratio": "P/B",
    "dividend_yield_pct": "Dividend Yield %",
    "interest_coverage": "ICR",
}

visible = visible.rename(columns=rename_columns)

numeric_columns = visible.select_dtypes(include="number").columns

visible[numeric_columns] = visible[numeric_columns].round(2)


st.dataframe(
    visible,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------

csv_bytes = visible.to_csv(index=False).encode("utf-8")


st.download_button(
    label="⬇️ Download Results as CSV",
    data=csv_bytes,
    file_name="nifty100_screener_results.csv",
    mime="text/csv",
)


# ---------------------------------------------------------------------
# Preset reference
# ---------------------------------------------------------------------

with st.expander("📋 Preset filter definitions"):
    st.markdown("""
        **Quality Compounder**
        - ROE ≥ 12%
        - D/E ≤ 1
        - FCF ≥ 0
        - Revenue CAGR 5Y ≥ 10%

        **Value Pick**
        - P/E ≤ 30
        - P/B ≤ 5
        - D/E ≤ 2
        - Dividend Yield ≥ 1.5%

        **Growth Accelerator**
        - PAT CAGR 5Y ≥ 20%
        - Revenue CAGR 5Y ≥ 15%
        - D/E ≤ 2

        **Dividend Champion**
        - Dividend Yield ≥ 1.5%
        - FCF ≥ 0

        **Debt-Free Blue Chip**
        - D/E = 0
        - ROE ≥ 12%

        **Turnaround Watch**
        - Revenue CAGR 3Y ≥ 10%
        """)
