\# NIFTY 100 Financial Intelligence Platform



A financial analytics and intelligence platform built for analyzing NIFTY 100 companies using financial statements, calculated financial ratios, growth metrics, screening rules, peer comparisons, capital allocation patterns, and valuation indicators.



The project combines an ETL/data-quality pipeline, financial KPI engine, configurable stock screener, peer analytics engine, valuation analysis, and an interactive Streamlit dashboard.



\---



\## Project Overview



The NIFTY 100 Financial Intelligence Platform is designed to transform raw company-level financial data into structured, decision-support analytics.



The platform supports:



\- Financial data ingestion and normalization

\- Data-quality validation

\- Financial ratio calculation

\- CAGR and growth analysis

\- Cash-flow and capital-allocation analysis

\- Multi-factor stock screening

\- Peer-group benchmarking

\- Percentile-based peer comparison

\- Valuation analysis

\- Interactive Streamlit dashboard

\- Downloadable analytical outputs

\- Automated test validation



The system currently covers \*\*92 valid companies\*\* from the supplied dataset.



\---



\## Key Features



\### 1. ETL and Data Quality



The ETL pipeline processes multiple financial datasets and loads them into structured analytical tables.



The pipeline handles:



\- Header normalization

\- Company-ID validation

\- Orphan-record detection

\- Duplicate detection and removal

\- Data validation

\- Financial-period normalization

\- Audit outputs

\- Rejected-record logging



Important data-quality outputs include:



```text

output/load\_audit.csv

output/rejected\_orphans.csv

output/deduplicated\_rows.csv

output/validation\_failures.csv

