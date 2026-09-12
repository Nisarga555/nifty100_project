import streamlit as st


st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.sidebar.title("📊 Nifty 100 Analytics")
    st.sidebar.markdown("---")

    st.sidebar.info(
        "Financial Intelligence Dashboard\n\n"
        "Sprint 4 — Dashboard + Valuation"
    )

    st.title("📊 Nifty 100 Analytics")
    st.subheader("Financial Intelligence Dashboard")

    st.markdown(
        """
        Welcome to the **Nifty 100 Financial Intelligence Platform**.

        Use the sidebar to explore:

        - 🏠 Home
        - 👤 Company Profile
        - 🔎 Screener
        - 👥 Peer Comparison
        - 📈 Trend Analysis
        - 🏭 Sector Analysis
        - 💰 Capital Allocation
        - 📑 Annual Reports
        """
    )

    st.success(
        "Dashboard scaffold is running successfully. "
        "Individual screens will be populated during Sprint 4."
    )


if __name__ == "__main__":
    main()