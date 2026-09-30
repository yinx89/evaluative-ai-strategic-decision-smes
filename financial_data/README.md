# Financial data

## Source and licence — read before reuse

The file `financials.csv` contains financial reporting facts extracted from
**UK Companies House** iXBRL accounts filings, retrieved through the Companies
House public API.

**This data is not covered by the MIT licence that applies to the code in this
repository.** It is public sector information made available by Companies House
under the **Open Government Licence v3.0**, and any reuse must comply with that
licence, including its attribution requirement:

> Contains public sector information licensed under the Open Government Licence v3.0.
> https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

## Contents

| Column | Meaning |
|---|---|
| `company_number` | Companies House registered company number |
| `filing_type` | Type of filing the fact was extracted from |
| `filing_date` | Date of the filing |
| `period` | Reporting period the fact refers to |
| `concept` | iXBRL reporting concept |
| `context` | iXBRL context reference |
| `value` | Reported value |
| `unit` | Unit of the reported value |

The file holds company-level reporting facts only. It contains no personal data:
officer and person-with-significant-control records retrieved by the ingestion
layer are not included in this dataset and are not published.

## Attribution for the selection

The selection, extraction and structuring of these facts is the work of this
project's authors and is released under **CC BY 4.0**. The underlying records
remain subject to the Open Government Licence v3.0 as stated above.
