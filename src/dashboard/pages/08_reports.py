import pandas as pd
import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_documents,
)


st.set_page_config(
    page_title="Annual Reports | Nifty 100 Analytics",
    page_icon="📑",
    layout="wide",
)


st.title("📑 Annual Reports")
st.caption(
    "Find available company annual-report documents."
)


# ---------------------------------------------------------------------
# Company search
# ---------------------------------------------------------------------

companies = get_companies()

if companies.empty:
    st.error(
        "Company data is unavailable."
    )
    st.stop()


companies = companies.copy()

companies["ticker"] = (
    companies["id"]
    .astype(str)
    .str.strip()
    .str.upper()
)

companies["company_name"] = (
    companies["company_name"]
    .fillna("")
    .astype(str)
)

companies["label"] = (
    companies["ticker"]
    + " — "
    + companies["company_name"]
)


search = st.text_input(
    "🔎 Search company or ticker",
    placeholder="Type a company name or ticker",
)


if search.strip():

    q = search.strip().lower()

    matches = companies[
        companies["ticker"]
        .str.lower()
        .str.contains(
            q,
            na=False,
        )
        |
        companies["company_name"]
        .str.lower()
        .str.contains(
            q,
            na=False,
        )
    ]

else:

    matches = companies


if matches.empty:
    st.warning(
        "Ticker not found — please try another"
    )
    st.stop()


selected_label = st.selectbox(
    "Select company",
    matches["label"].head(20).tolist(),
)


ticker = selected_label.split(
    " — "
)[0].strip().upper()


company_name = companies.loc[
    companies["ticker"] == ticker,
    "company_name",
].iloc[0]


st.subheader(
    f"📚 Annual Reports — {company_name}"
)


# ---------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------

documents = get_documents(ticker)


if documents.empty:
    st.info(
        "No annual report records are available "
        "for this company."
    )
    st.stop()


# ---------------------------------------------------------------------
# Detect useful columns
# ---------------------------------------------------------------------

year_column = next(
    (
        column
        for column in [
            "year",
            "financial_year",
            "report_year",
            "fy",
        ]
        if column in documents.columns
    ),
    None,
)


url_column = next(
    (
        column
        for column in [
            "bse_pdf",
            "bse_pdf_link",
            "pdf_url",
            "report_url",
            "document_url",
            "url",
            "link",
        ]
        if column in documents.columns
    ),
    None,
)


# If no obvious URL column exists, look for a column
# containing URL-like values.
if url_column is None:

    for column in documents.columns:

        values = (
            documents[column]
            .dropna()
            .astype(str)
        )

        if not values.empty:

            if values.str.contains(
                r"https?://",
                regex=True,
                na=False,
            ).any():

                url_column = column
                break


# ---------------------------------------------------------------------
# Display reports
# ---------------------------------------------------------------------

display_rows = []


for _, row in documents.iterrows():

    year = (
        row[year_column]
        if year_column
        else "Available"
    )

    url = (
        str(row[url_column]).strip()
        if url_column
        and pd.notna(row[url_column])
        else ""
    )

    if url.lower() in [
        "",
        "nan",
        "none",
        "null",
    ]:
        status = "Report unavailable"
    else:
        status = "Report available"

    display_rows.append(
        {
            "Year": str(year),
            "URL": url,
            "Status": status,
        }
    )


reports = pd.DataFrame(
    display_rows
)


if reports.empty:
    st.info(
        "No annual report records are available."
    )
    st.stop()


# Sort newest first where possible
if "Year" in reports.columns:

    reports["_sort_year"] = pd.to_numeric(
        reports["Year"]
        .astype(str)
        .str.extract(
            r"(\d{4})"
        )[0],
        errors="coerce",
    )

    reports = reports.sort_values(
        "_sort_year",
        ascending=False,
        na_position="last",
    )


# ---------------------------------------------------------------------
# Report cards
# ---------------------------------------------------------------------

for _, report in reports.iterrows():

    year = report["Year"]
    url = report["URL"]
    status = report["Status"]

    left, middle, right = st.columns(
        [2, 4, 2]
    )

    with left:
        st.markdown(
            f"### 📄 {year}"
        )

    with middle:

        if status == "Report available":

            st.markdown(
                f"[🔗 Open BSE / PDF Report]({url})"
            )

        else:

            st.markdown(
                "Report unavailable"
            )

    with right:

        if status == "Report available":
            st.success("Available")
        else:
            st.error("Unavailable")


st.divider()

st.caption(
    "Report availability is based on the document URLs present "
    "in the project source data."
)