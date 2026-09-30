# Towards an Evaluative AI Framework for Hypothesis-Driven Strategic Decision-Making in SMEs

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23065542.svg)](https://doi.org/10.5281/zenodo.23065542)

> ⚠️ This is an ongoing work, being developed as part of a three-year industrial PhD project. Regular updates and improvements will be made based on feedback and research findings.

This repository implements a process-centric Evaluative AI (EAI) framework designed to address strategic decision-making challenges in SMEs. The framework integrates:
- Hypothesis-driven evaluation
- Modular multi-agent architecture
- Iterative refinement of business hypotheses
- Integration with Companies House data and internal business metrics
- Local execution using open-source LLMs for data confidentiality

The system uses specialized agents to evaluate patterns, profitability, and risk within specific business contexts, leveraging both internal company data and trustworthy public sources.owards an Evaluative AI Framework for Hypothesis-Driven Strategic Decision-Making in SMEs

This repository contains a data collection and processing framework for analyzing UK software consultancy companies. It fetches company data from Companies House API and processes their financial information to support strategic decision-making in SMEs.

## 🏗 Technical Architecture

The framework implements a modular and adaptive design that includes:
- Local execution using open-source LLMs (currently `gpt-oss` 20.9B parameters via Ollama)
- Pydantic AI for agent creation and LangGraph for workflow orchestration
- Specialized agents for financial analysis and domain-specific reasoning
- Built-in reflection layer for agent self-assessment and improvement
- Support for hypothesis testing across different scenarios
- State persistence for revisiting and branching decision scenarios
- Human-in-the-loop interactions for reliability and oversight

## ✨ Features
- Companies House API integration for company data retrieval
- Financial data processing and KPI generation
- Data caching for efficient API usage
- Support for multiple SIC codes filtering
- Automated metrics calculation

## ⚙️ Workflow

### 1 - Ingestion Phase

(See analysis/metadata_and_extra_info/ingestion.md for more information.)

Follow these steps to set up and run the ingestion process:

1. Create a Python virtual environment:
    ```bash
    python3 -m venv venv
    ```

2. Activate the virtual environment:
    ```bash
    source venv/bin/activate  # On Unix/macOS
    # or
    venv\Scripts\activate     # On Windows
    ```

3. Install dependencies:
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

4. Run the ingestion script:
    ```bash
    python3 ./ingest/companies_house_data.py --sic-codes "62020" --use-cache y
    ```

Parameters explained:
- `--sic-codes`: Standard Industrial Classification codes to filter companies. Example:
  - "62020" (Default): Computer consultancy activities
  - Multiple codes can be comma-separated: "62020,62021"
- `--use-cache`: Cache management (true/False)
  - "False" (Default): Force fresh data fetch from Companies House API
  - "true": Use existing cached data if available

### 2 - Financial Data Processing

After ingesting the company data, you can process financial information:

1. Ensure your virtual environment is activated
2. Run the financial data processing script:
```bash
python3 ./process/get_financial_data.py
```

The script will:
- Read company data from `company_details` folder
- Process and normalize financial metrics
- Generate key performance indicators (KPIs)
- Save processed data to `financial_data` folder

### 3 - Decision-Making Process

> 🚧 This section is actively under development and will be updated with implementation details, examples, and documentation as soon as available.

The framework can be triggered via:
- Streamlit interface
- LangGraph Studio
- API endpoints

The system follows these steps:
1. Loads or updates business configuration and memory
2. Orchestrator-reasoner agent coordinates specialized agents
3. Agents perform analysis including:
   - Pattern recognition
   - Profitability assessment
   - Risk evaluation
   - Stress testing
   - Data validation
4. Results are presented with detailed logs for analysis
5. State is preserved for scenario comparison and branching

## 🔒 Personal data

**This project processes no personal data.**

The Companies House API exposes personal data in several places, and the
ingestion layer is built to avoid all of them:

- The **officers** and **persons-with-significant-control** endpoints return
  named individuals. They are not queried at all.
- The **filing history** is needed for its dates, categories and form types, but
  its `description_values` block also carries officer and PSC names and, on
  address-change filings, residential addresses. Those fields are stripped at
  ingestion by `_strip_personal_fields` in `ingest/companies_house_data.py`.

Nothing personal is therefore written to disk or reaches any output. This is
data minimisation in the sense of Art. 5(1)(c) GDPR, and no special categories
of personal data under Art. 9 GDPR are involved at any point.

Verified against 337 stored company records covering 8,425 filing-history
entries: 1,613 of them carried a personal name before this change and none does
after it, while all 6,290 entries carrying the dates the analysis uses are
preserved unchanged.

## 📚 Citation

If you use this software in academic publications or derived projects, please cite the paper it accompanies:

> Molina-Abril, G., Calvet, L., Riera, D. (2026). Towards an Evaluative AI Framework for Hypothesis-Driven Strategic Decision-Making in SMEs. In: Martínez, L., et al. *Intelligent Data Engineering and Automated Learning – IDEAL 2025*. IDEAL 2025. Lecture Notes in Computer Science, vol 16238. Springer, Cham. https://doi.org/10.1007/978-3-032-10486-1_34

The accepted manuscript is freely available at https://molina-abril.github.io and deposited in the UOC institutional repository O2 (https://hdl.handle.net/10609/156324, publicly available from 7 November 2026).

You can also use the [`CITATION.cff`](./CITATION.cff) file to import the citation directly into reference managers.

## 🪪 License

Distributed under the terms of the [MIT License](./LICENSE).

**The MIT licence covers the code only.** The dataset in
[`financial_data/`](./financial_data/) is derived from UK Companies House public
records and is covered separately: see
[`financial_data/README.md`](./financial_data/README.md). It contains public
sector information licensed under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
