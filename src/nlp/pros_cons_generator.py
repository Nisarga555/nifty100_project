import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================
# FILES
# ============================================================

DB_FILE = Path("db/nifty100.sqlite3")

PL_FILE = Path("data/raw/profitandloss.xlsx")
BS_FILE = Path("data/raw/balancesheet.xlsx")
CF_FILE = Path("data/raw/cashflow.xlsx")
SECTOR_FILE = Path("data/raw/sectors.xlsx")
MARKET_CAP_FILE = Path("data/raw/market_cap.xlsx")

OUTPUT_FILE = Path("output/pros_cons_generated.csv")


# ============================================================
# EXACT SPRINT 5 RULE TEXTS
# ============================================================

PRO_RULES = {
    1: "Consistently high return on equity above 20% demonstrates exceptional capital efficiency",
    2: "Strong free cash flow generation over 5 years signals healthy business fundamentals",
    3: "Debt-free balance sheet provides financial flexibility and eliminates interest burden",
    4: "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum",
    5: "Operating profit margin above 25% indicates strong pricing power and cost discipline",
    6: "Net profit compounding at above 20% over 5 years creates significant shareholder value",
    7: "Very high interest coverage ratio reflects negligible financial stress from debt servicing",
    8: "Consistent dividend yield above 2% backed by positive free cash flow",
    9: "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding",
    10: "Return on equity improving for 3 consecutive years shows strengthening business quality",
    11: "Revenue growing slower than profits shows improving operating leverage and scale benefits",
    12: "Growing asset base funded by internal accruals reflects self-sustaining growth",
}


CON_RULES = {
    1: "Debt-to-equity ratio of {value} is elevated for a non-financial company and warrants monitoring",
    2: "Free cash flow negative for 3 consecutive years raises concern about cash generation quality",
    3: "Operating margins declining for 3 consecutive years suggest pricing or cost pressure",
    4: "Company reported a net loss in the most recent financial year",
    5: "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss",
    6: "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations",
    7: "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable",
    8: "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk",
    9: "Earnings per share declining for 3 consecutive years reflects deteriorating profitability",
    10: "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital",
    11: "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility",
    12: "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum",
}


# ============================================================
# HELPERS
# ============================================================


def clean_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def clean_ids(df):
    df = df.copy()

    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()

    return df


def add_year_number(df):
    """
    Add numeric year from strings such as:
    Mar 2019
    Dec 2020
    Sep 2024
    """

    df = df.copy()

    if "year" not in df.columns:
        raise ValueError("Expected 'year' column was not found.")

    df["year_num"] = df["year"].astype(str).str.extract(r"(\d{4})")[0]

    df["year_num"] = pd.to_numeric(df["year_num"], errors="coerce")

    return df.dropna(subset=["year_num"])


def latest_rows(df):
    df = add_year_number(df)

    return (
        df.sort_values(["company_id", "year_num"])
        .groupby("company_id", as_index=False)
        .tail(1)
        .copy()
    )


def consecutive_increase(values, periods):
    values = list(values)

    if len(values) < periods + 1:
        return False

    recent = values[-(periods + 1) :]

    if any(pd.isna(x) for x in recent):
        return False

    return all(recent[i] > recent[i - 1] for i in range(1, len(recent)))


def consecutive_decrease(values, periods):
    values = list(values)

    if len(values) < periods + 1:
        return False

    recent = values[-(periods + 1) :]

    if any(pd.isna(x) for x in recent):
        return False

    return all(recent[i] < recent[i - 1] for i in range(1, len(recent)))


def confidence_above_threshold(
    value,
    threshold,
    base=70,
    scale=1.5,
):
    if pd.isna(value):
        return None

    margin = float(value) - float(threshold)

    if margin <= 0:
        return None

    confidence = base + margin * scale

    return int(min(99, max(61, round(confidence))))


def binary_confidence(value):
    return int(min(99, max(61, value)))


def is_financial_sector(sector):
    if pd.isna(sector):
        return False

    text = str(sector).lower()

    keywords = [
        "financial",
        "bank",
        "insurance",
        "nbfc",
    ]

    return any(keyword in text for keyword in keywords)


# ============================================================
# LOAD DATA
# ============================================================


def load_data():

    print("Loading source data...")

    pl = clean_ids(clean_columns(pd.read_excel(PL_FILE, header=1)))

    bs = clean_ids(clean_columns(pd.read_excel(BS_FILE, header=1)))

    cf = clean_ids(clean_columns(pd.read_excel(CF_FILE, header=1)))

    sectors = clean_ids(clean_columns(pd.read_excel(SECTOR_FILE, header=0)))

    # --------------------------------------------------------
    # Market cap is NOT assumed to have a year column.
    # --------------------------------------------------------

    market_cap = clean_ids(clean_columns(pd.read_excel(MARKET_CAP_FILE, header=0)))

    # Add years only to files that actually contain them.
    pl = add_year_number(pl)
    bs = add_year_number(bs)
    cf = add_year_number(cf)

    conn = sqlite3.connect(DB_FILE)

    ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)

    conn.close()

    ratios = clean_ids(ratios)
    ratios = add_year_number(ratios)

    return (
        pl,
        bs,
        cf,
        ratios,
        sectors,
        market_cap,
    )


# ============================================================
# GENERATOR
# ============================================================


def generate():

    (
        pl,
        bs,
        cf,
        ratios,
        sectors,
        market_cap,
    ) = load_data()

    company_ids = sorted(
        set(ratios["company_id"].dropna().astype(str).str.strip().str.upper())
    )

    print(f"Company universe: {len(company_ids)}")

    latest_ratio = latest_rows(ratios).set_index("company_id")

    latest_pl = latest_rows(pl).set_index("company_id")

    latest_bs = latest_rows(bs).set_index("company_id")

    # --------------------------------------------------------
    # Sector lookup
    # --------------------------------------------------------

    sector_lookup = {}

    for _, row in sectors.iterrows():

        company_id = str(row["company_id"]).strip().upper()

        broad = row.get("broad_sector", "")

        sector_lookup[company_id] = "" if pd.isna(broad) else str(broad)

    # --------------------------------------------------------
    # FCF history
    # --------------------------------------------------------

    cf = cf.copy()

    cf["free_cash_flow"] = pd.to_numeric(
        cf["operating_activity"], errors="coerce"
    ) + pd.to_numeric(cf["investing_activity"], errors="coerce")

    cf = cf.sort_values(["company_id", "year_num"])

    # --------------------------------------------------------
    # P&L history
    # --------------------------------------------------------

    pl = pl.sort_values(["company_id", "year_num"])

    # --------------------------------------------------------
    # Balance Sheet history
    # --------------------------------------------------------

    bs = bs.sort_values(["company_id", "year_num"])

    output = []

    for company_id in company_ids:

        sector = sector_lookup.get(company_id, "")

        financial_company = is_financial_sector(sector)

        company_ratio = ratios[ratios["company_id"] == company_id].sort_values(
            "year_num"
        )

        company_pl = pl[pl["company_id"] == company_id].sort_values("year_num")

        company_bs = bs[bs["company_id"] == company_id].sort_values("year_num")

        company_cf = cf[cf["company_id"] == company_id].sort_values("year_num")

        if company_id not in latest_ratio.index:
            continue

        r = latest_ratio.loc[company_id]

        roe = r.get("return_on_equity_pct", np.nan)

        roce = r.get("return_on_capital_employed_pct", np.nan)

        de = r.get("debt_to_equity", np.nan)

        icr = r.get("interest_coverage", np.nan)

        revenue_cagr_5 = r.get("revenue_cagr_5yr", np.nan)

        pat_cagr_5 = r.get("pat_cagr_5yr", np.nan)

        eps_cagr_5 = r.get("eps_cagr_5yr", np.nan)

        opm = r.get("operating_profit_margin_pct", np.nan)

        dividend_payout = r.get("dividend_payout_ratio_pct", np.nan)

        # ====================================================
        # FCF
        # ====================================================

        fcf_values = (
            pd.to_numeric(company_cf["free_cash_flow"], errors="coerce")
            .dropna()
            .tolist()
        )

        latest_fcf = fcf_values[-1] if fcf_values else np.nan

        # ====================================================
        # PRO 1
        # ====================================================

        roe_history = (
            pd.to_numeric(company_ratio["return_on_equity_pct"], errors="coerce")
            .dropna()
            .tolist()
        )

        if len(roe_history) >= 3 and all(x > 20 for x in roe_history[-3:]):

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P01",
                    "text": PRO_RULES[1],
                    "confidence_pct": binary_confidence(85),
                }
            )

        # ====================================================
        # PRO 2
        # ====================================================

        if len(fcf_values) >= 5 and all(x > 0 for x in fcf_values[-5:]):

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P02",
                    "text": PRO_RULES[2],
                    "confidence_pct": binary_confidence(90),
                }
            )

        # ====================================================
        # PRO 3
        # ====================================================

        if pd.notna(de) and abs(float(de)) < 1e-9:

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P03",
                    "text": PRO_RULES[3],
                    "confidence_pct": binary_confidence(95),
                }
            )

        # ====================================================
        # PRO 4
        # ====================================================

        confidence = confidence_above_threshold(revenue_cagr_5, 15)

        if confidence:

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P04",
                    "text": PRO_RULES[4],
                    "confidence_pct": confidence,
                }
            )

        # ====================================================
        # PRO 5
        # ====================================================

        confidence = confidence_above_threshold(opm, 25)

        if confidence:

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P05",
                    "text": PRO_RULES[5],
                    "confidence_pct": confidence,
                }
            )

        # ====================================================
        # PRO 6
        # ====================================================

        confidence = confidence_above_threshold(pat_cagr_5, 20)

        if confidence:

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P06",
                    "text": PRO_RULES[6],
                    "confidence_pct": confidence,
                }
            )

        # ====================================================
        # PRO 7
        # ====================================================

        debt_free = pd.notna(de) and abs(float(de)) < 1e-9

        high_icr = pd.notna(icr) and float(icr) > 10

        if debt_free or high_icr:

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P07",
                    "text": PRO_RULES[7],
                    "confidence_pct": binary_confidence(95 if debt_free else 85),
                }
            )

        # ====================================================
        # PRO 8
        #
        # Market cap file structure will be inspected later
        # if dividend yield is not directly available.
        # ====================================================

        dividend_yield = np.nan

        if "dividend_yield_pct" in market_cap.columns:

            company_market = market_cap[market_cap["company_id"] == company_id]

            if not company_market.empty:

                value = company_market["dividend_yield_pct"].dropna()

                if not value.empty:
                    dividend_yield = float(value.iloc[-1])

        if (
            pd.notna(dividend_yield)
            and dividend_yield > 2
            and pd.notna(latest_fcf)
            and latest_fcf > 0
        ):

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P08",
                    "text": PRO_RULES[8],
                    "confidence_pct": binary_confidence(85),
                }
            )

        # ====================================================
        # PRO 9
        # ====================================================

        confidence = confidence_above_threshold(eps_cagr_5, 15)

        if confidence:

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P09",
                    "text": PRO_RULES[9],
                    "confidence_pct": confidence,
                }
            )

        # ====================================================
        # PRO 10
        # ====================================================

        if consecutive_increase(roe_history, 3):

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P10",
                    "text": PRO_RULES[10],
                    "confidence_pct": binary_confidence(85),
                }
            )

        # ====================================================
        # PRO 11
        # ====================================================

        if (
            pd.notna(pat_cagr_5)
            and pd.notna(revenue_cagr_5)
            and float(pat_cagr_5) > float(revenue_cagr_5)
        ):

            output.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": "P11",
                    "text": PRO_RULES[11],
                    "confidence_pct": binary_confidence(78),
                }
            )

        # ====================================================
        # PRO 12
        # ====================================================

        if len(company_bs) >= 2:

            assets = (
                pd.to_numeric(company_bs["total_assets"], errors="coerce")
                .dropna()
                .tolist()
            )

            debt = (
                pd.to_numeric(company_bs["borrowings"], errors="coerce")
                .dropna()
                .tolist()
            )

            if (
                len(assets) >= 2
                and len(debt) >= 2
                and assets[-1] > assets[-2]
                and debt[-1] < debt[-2]
            ):

                output.append(
                    {
                        "company_id": company_id,
                        "type": "pro",
                        "rule_id": "P12",
                        "text": PRO_RULES[12],
                        "confidence_pct": binary_confidence(82),
                    }
                )

        # ====================================================
        # CON 1
        # ====================================================

        if not financial_company and pd.notna(de) and float(de) > 2:

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C01",
                    "text": CON_RULES[1].format(value=f"{float(de):.2f}"),
                    "confidence_pct": binary_confidence(85),
                }
            )

        # ====================================================
        # CON 2
        # ====================================================

        if len(fcf_values) >= 3 and all(x < 0 for x in fcf_values[-3:]):

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C02",
                    "text": CON_RULES[2],
                    "confidence_pct": binary_confidence(90),
                }
            )

        # ====================================================
        # CON 3
        # ====================================================

        opm_history = (
            pd.to_numeric(company_ratio["operating_profit_margin_pct"], errors="coerce")
            .dropna()
            .tolist()
        )

        if consecutive_decrease(opm_history, 3):

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C03",
                    "text": CON_RULES[3],
                    "confidence_pct": binary_confidence(88),
                }
            )

        # ====================================================
        # CON 4
        # ====================================================

        if company_id in latest_pl.index:

            net_profit = pd.to_numeric(
                latest_pl.loc[company_id].get("net_profit", np.nan), errors="coerce"
            )

            if pd.notna(net_profit) and net_profit < 0:

                output.append(
                    {
                        "company_id": company_id,
                        "type": "con",
                        "rule_id": "C04",
                        "text": CON_RULES[4],
                        "confidence_pct": binary_confidence(95),
                    }
                )

        # ====================================================
        # CON 5
        # ====================================================

        revenue_history = (
            pd.to_numeric(company_pl["sales"], errors="coerce").dropna().tolist()
        )

        if consecutive_decrease(revenue_history, 2):

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C05",
                    "text": CON_RULES[5],
                    "confidence_pct": binary_confidence(88),
                }
            )

        # ====================================================
        # CON 6
        # ====================================================

        if pd.notna(icr) and float(icr) < 1.5:

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C06",
                    "text": CON_RULES[6],
                    "confidence_pct": binary_confidence(92),
                }
            )

        # ====================================================
        # CON 7
        # ====================================================

        if pd.notna(dividend_payout) and float(dividend_payout) > 100:

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C07",
                    "text": CON_RULES[7],
                    "confidence_pct": binary_confidence(92),
                }
            )

        # ====================================================
        # CON 8
        # ====================================================

        de_history = (
            pd.to_numeric(company_ratio["debt_to_equity"], errors="coerce")
            .dropna()
            .tolist()
        )

        if consecutive_increase(de_history, 3):

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C08",
                    "text": CON_RULES[8],
                    "confidence_pct": binary_confidence(88),
                }
            )

        # ====================================================
        # CON 9
        # ====================================================

        eps_history = (
            pd.to_numeric(company_pl["eps"], errors="coerce").dropna().tolist()
        )

        if consecutive_decrease(eps_history, 3):

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C09",
                    "text": CON_RULES[9],
                    "confidence_pct": binary_confidence(90),
                }
            )

        # ====================================================
        # CON 10
        # ====================================================

        if pd.notna(roce) and float(roce) < 10:

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C10",
                    "text": CON_RULES[10],
                    "confidence_pct": binary_confidence(90),
                }
            )

        # ====================================================
        # CON 11
        # ====================================================

        if company_id in latest_bs.index:

            borrowings = pd.to_numeric(
                latest_bs.loc[company_id].get("borrowings", np.nan), errors="coerce"
            )

            investments = pd.to_numeric(
                latest_bs.loc[company_id].get("investments", np.nan), errors="coerce"
            )

            if pd.notna(borrowings) and pd.notna(investments):

                net_debt = borrowings - investments

                if company_id in latest_pl.index:

                    operating_profit = pd.to_numeric(
                        latest_pl.loc[company_id].get("operating_profit", np.nan),
                        errors="coerce",
                    )

                    depreciation = pd.to_numeric(
                        latest_pl.loc[company_id].get("depreciation", np.nan),
                        errors="coerce",
                    )

                    if pd.notna(operating_profit) and pd.notna(depreciation):

                        ebitda = operating_profit + depreciation

                        if ebitda > 0 and net_debt > 3 * ebitda:

                            output.append(
                                {
                                    "company_id": company_id,
                                    "type": "con",
                                    "rule_id": "C11",
                                    "text": CON_RULES[11],
                                    "confidence_pct": binary_confidence(90),
                                }
                            )

        # ====================================================
        # CON 12
        # ====================================================

        if pd.notna(revenue_cagr_5) and float(revenue_cagr_5) < 5:

            output.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": "C12",
                    "text": CON_RULES[12],
                    "confidence_pct": binary_confidence(82),
                }
            )

    # ========================================================
    # BUILD RESULT
    # ========================================================

    result = pd.DataFrame(
        output,
        columns=[
            "company_id",
            "type",
            "rule_id",
            "text",
            "confidence_pct",
        ],
    )

    # Sprint requirement: confidence >60%
    result = result[result["confidence_pct"] > 60].copy()

    result = result.drop_duplicates(
        subset=[
            "company_id",
            "type",
            "rule_id",
        ]
    )

    result = result.sort_values(
        [
            "company_id",
            "type",
            "rule_id",
        ]
    ).reset_index(drop=True)

    # ========================================================
    # COVERAGE
    # ========================================================

    pro_companies = set(result.loc[result["type"] == "pro", "company_id"])

    con_companies = set(result.loc[result["type"] == "con", "company_id"])

    missing_pro = sorted(set(company_ids) - pro_companies)

    missing_con = sorted(set(company_ids) - con_companies)

    # ========================================================
    # OUTPUT
    # ========================================================

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(OUTPUT_FILE, index=False)

    print()
    print("=" * 65)
    print("NLP PROS & CONS GENERATOR")
    print("=" * 65)

    print(f"Companies processed : {len(company_ids)}")

    print(f"Total signals       : {len(result)}")

    print(f"Pro signals         : " f"{len(result[result['type'] == 'pro'])}")

    print(f"Con signals         : " f"{len(result[result['type'] == 'con'])}")

    print()
    print(f"Companies with Pro  : " f"{len(pro_companies)}")

    print(f"Companies with Con  : " f"{len(con_companies)}")

    print()

    if missing_pro:
        print("COMPANIES MISSING PRO:")
        print(", ".join(missing_pro))
    else:
        print("Every company has at least 1 Pro: YES")

    if missing_con:
        print("COMPANIES MISSING CON:")
        print(", ".join(missing_con))
    else:
        print("Every company has at least 1 Con: YES")

    print()
    print("Signals by rule:")

    if not result.empty:
        print(result["rule_id"].value_counts().sort_index().to_string())

    print()
    print("Confidence range:")

    if not result.empty:
        print(
            f"{result['confidence_pct'].min()} - " f"{result['confidence_pct'].max()}"
        )

    print()
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate()
