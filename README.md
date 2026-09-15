# NIFTY 100 Financial Intelligence Platform

A comprehensive financial intelligence and analytics platform for analyzing NIFTY 100 companies using financial statements, financial ratios, cash-flow quality, peer comparison, screening, valuation, NLP-based analysis, clustering, and interactive dashboards.

---

## Project Overview

The NIFTY 100 Financial Intelligence Platform converts raw financial and market data into structured analytics and decision-support outputs.

The platform combines:

- Data ingestion and ETL
- Data quality validation
- Financial ratio calculation
- CAGR analysis
- Cash-flow intelligence
- Stock screening
- Composite financial scoring
- Peer comparison
- Sector analysis
- Relative valuation
- NLP-based financial analysis
- KMeans company clustering
- Portfolio-level statistics
- Automated company tearsheets
- FastAPI REST API
- Streamlit interactive dashboard
- Automated testing

The system processes data for **92 companies available in the supplied source dataset**.

---

## Key Capabilities

### 1. Data Engineering

Raw Excel datasets are processed and loaded into a SQLite analytical database.

The ETL pipeline performs:

- Schema validation
- Column normalization
- Company-ID validation
- Duplicate detection
- Orphan-record detection
- Data-quality reporting
- Source reconciliation

Generated audit files include:

- `load_audit.csv`
- `rejected_orphans.csv`
- `deduplicated_rows.csv`
- `validation_failures.csv`

---

### 2. Financial Ratio Engine

The platform calculates and validates major financial ratios including:

- Net Profit Margin
- Operating Profit Margin
- Return on Equity
- Return on Capital Employed
- Return on Assets
- Debt-to-Equity
- Interest Coverage Ratio
- Asset Turnover
- CFO/PAT Ratio
- Free Cash Flow

The engine also handles financial edge cases such as:

- Zero sales
- Zero interest
- Debt-free companies
- Negative equity
- Negative earnings
- Sector-specific leverage interpretation

---

### 3. CAGR Analysis

Historical growth is calculated for:

- Revenue CAGR
- PAT CAGR
- EPS CAGR

Supported periods include:

- 3 years
- 5 years
- 10 years

The CAGR engine also identifies conditions such as:

- Growth decline
- Turnarounds
- Loss-to-profit transitions
- Both-negative periods
- Zero-base cases
- Insufficient historical data

Historical values are not fabricated when required periods are unavailable.

---

## Stock Screener

The platform provides multiple predefined screening strategies.

### Quality Compounder

Criteria include:

- ROE >= 12%
- Debt-to-Equity <= 1
- Positive FCF
- Revenue CAGR >= 10%

### Value Pick

Criteria include:

- P/E <= 30
- P/B <= 5
- Debt-to-Equity <= 2
- Dividend Yield >= 1.5%

### Growth Accelerator

Criteria include:

- PAT CAGR >= 20%
- Revenue CAGR >= 15%
- Debt-to-Equity <= 2

### Dividend Champion

Criteria include:

- Dividend Yield >= 1.5%
- Dividend payout <= 80%
- Positive FCF

### Debt-Free Blue Chip

Criteria include:

- Debt-to-Equity = 0
- ROE >= 12%
- Sales >= 5000 crore

### Turnaround Watch

Criteria include:

- Revenue CAGR 3Y >= 10%
- Positive latest FCF
- Declining Debt-to-Equity

---

## Composite Scoring

Companies are scored using a weighted financial-quality model.

### Profitability — 35%

- ROE — 15%
- ROCE — 10%
- Net Profit Margin — 10%

### Cash Quality — 30%

- FCF growth — 15%
- CFO/PAT — 10%
- Positive FCF — 5%

### Growth — 20%

- Revenue CAGR — 10%
- PAT CAGR — 10%

### Leverage — 15%

- Debt-to-Equity — 10%
- Interest Coverage — 5%

The scoring system uses sector-relative normalization and percentile-based winsorization.

---

## Peer Analysis

Companies are grouped into peer categories including:

- Automobiles
- FMCG
- Power & Utilities
- Private Banks
- IT Services
- Pharmaceuticals
- Oil & Gas
- Public Sector Banks
- Life Insurance
- Steel
- Consumer Finance

Peer analytics include percentile rankings for financial metrics.

Debt-to-equity is treated as an inverse metric because lower leverage is generally preferable.

Outputs include:

- Peer percentile data
- Peer comparison workbook
- Radar charts
- Peer-group comparisons

---

## Valuation Engine

The valuation module provides relative valuation intelligence using:

- Free Cash Flow Yield
- Historical 5-year median P/E
- Sector median P/E

Companies are classified as:

- `Discount`
- `Fair`
- `Caution`

Relative P/E thresholds:

- P/E < 70% of sector median → Discount
- P/E between 70% and 150% → Fair
- P/E > 150% → Caution

---

## Cash-Flow Intelligence

The cash-flow module analyzes:

- Operating cash flow
- Investing cash flow
- Financing cash flow
- Free cash flow
- CFO/PAT quality
- CapEx intensity
- Capital allocation

Capital allocation patterns include:

- Shareholder Returns
- Mixed
- Reinvestor
- Growth Funded by Debt
- Liquidating Assets
- Distress Signal
- Pre-Revenue

The system also produces distress and deleveraging alerts.

---

## NLP Financial Analysis

The platform parses textual financial-analysis fields from the source dataset.

Parsed metrics include:

- Compounded Sales Growth
- Compounded Profit Growth
- Stock Price CAGR
- ROE

The parser extracts:

- Period in years
- Percentage value

Example:

`5 Years: 24%`

becomes:

- Period: 5 years
- Value: 24%

Parsing failures are separately logged rather than silently discarded.

The NLP layer also generates structured Pros and Cons for companies based on available financial information.

---

## Company Clustering

The platform applies **KMeans clustering** to group companies according to financial characteristics.

The clustering pipeline uses:

- StandardScaler
- KMeans
- 5 clusters
- `random_state=42`
- `n_init=20`

The resulting five financial archetypes are:

1. Balanced Compounder
2. Growth Accelerator
3. High-ROE Leader
4. Value & Cash Flow
5. Debt-Free Compounder

All 92 companies receive a cluster assignment.

Outputs include:

- Cluster labels
- Cluster profiles
- Distance from centroid
- Outlier analysis
- Portfolio statistics
- Correlation heatmap
- Elbow plot

---

## Portfolio Analytics

Portfolio-level statistics are generated for major financial KPIs.

The analysis includes:

- P10
- P25
- Median
- P75
- P90
- Mean
- Standard deviation
- Company count

This allows individual companies to be evaluated relative to the broader dataset.

---

## Automated Company Tearsheets

The reporting engine generates individual PDF tearsheets for companies.

The tearsheets contain financial intelligence and supporting analysis.

Generated:

- 92 company tearsheets
- Sector-level reports
- NIFTY 100 Overall report
- Portfolio summary report

The portfolio report contains **93 pages**, including the cover and company-level pages.

---

# Interactive Dashboard

The project includes a Streamlit dashboard with 8 screens.

The dashboard provides access to:

- Company overview
- Financial statements
- Financial ratios
- Screening
- Peer analysis
- Sector analysis
- Valuation
- Reports

The dashboard uses cached database queries to improve responsiveness.

---

# REST API

A FastAPI backend exposes the analytics through REST endpoints.

Base API:

`/api/v1`

## Available Endpoints

### Companies

```text
GET /api/v1/companies
GET /api/v1/companies/{ticker}
GET /api/v1/companies/{ticker}/pl
GET /api/v1/companies/{ticker}/bs
GET /api/v1/companies/{ticker}/cashflow
GET /api/v1/companies/{ticker}/ratios
GET /api/v1/companies/{ticker}/tearsheet