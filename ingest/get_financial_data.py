import plotly.express as px
import duckdb
import pandas as pd

con = duckdb.connect()

query = """
WITH financial_facts AS (
    SELECT 
        company_number,
        filing.filing_type,
        filing.filing_date,
        unnest.period as period,
        unnest.concept as concept,
        unnest.context as context,
        TRY_CAST(unnest.value AS FLOAT) as value,
        unnest.unit
    FROM (
        SELECT 
            company_number,
            UNNEST(financials) as filing
        FROM read_parquet('../company_details/*.parquet', union_by_name=True)
        WHERE financials IS NOT NULL
    ),
    UNNEST(filing.facts) AS unnest
    WHERE unnest.value IS NOT NULL
)
SELECT 
    company_number,
    filing_type,
    filing_date,
    period,
    concept,
    context,
    value,
    unit
FROM financial_facts
WHERE period IS NOT NULL
ORDER BY company_number, filing_date DESC, period DESC, concept ASC, context ASC;
"""

df_financials = con.execute(query).df()

df_financials.to_csv("../financial_data/financials.csv", index=False)