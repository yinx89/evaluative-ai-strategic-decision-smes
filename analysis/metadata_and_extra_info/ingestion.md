# Companies House Data Ingestion Process

## Initialization
```python
# Load configuration
LOAD environment_variables
SET api_key
SET sic_codes = [62020, 62030, 62090, 63110, 63120, 58290, 58210]
```

## Main Process

### Company Number Collection
```python
IF use_cache:
    company_numbers = LOAD from parquet files
ELSE:
    FOR each sic_code:
        IF total_companies <= 5000:
            GET companies directly
        ELSE:
            GET earliest_date using binary search
            WHILE more_companies_to_fetch:
                ADJUST time window size
                GET companies in window
        SAVE companies to parquet files
```

### Company Processing
```python
# Load progress tracking
GET processed_companies from parquet files
remaining_companies = company_numbers - processed_companies

# Process each company
FOR company IN remaining_companies:
    GET basic_info
    IF basic_info exists:
        GET additional_info:
            - filing_history
            - officers
            - financial_data
            - other_company_details
        
        IF company has accounts:
            GET filing_history
            FILTER accounts_filings
            SORT by date (most recent first)
            GET financial_data from iXBRL documents
        
        SAVE all data to {company_number}.parquet
```

## Error Handling
```python
HANDLE:
    - API timeouts
    - Rate limits
    - Interruptions
    SAVE progress on any error
```