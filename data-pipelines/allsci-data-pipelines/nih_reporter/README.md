# NIH RePORTER Data Pipeline

Comprehensive AWS CDK data pipeline for ingesting, processing, and analyzing NIH RePORTER (Research Portfolio Online Reporting Tools Expenditures and Results) grant and publication data.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Schema Design](#schema-design)
- [Installation](#installation)
- [Deployment](#deployment)
- [Usage](#usage)
- [Query Examples](#query-examples)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Overview

The NIH RePORTER pipeline automates the extraction, transformation, and loading (ETL) of NIH research project data, including:

- Grant awards and funding information
- Principal investigators and program officers
- Project abstracts and public health relevance
- Publications (PubMed links)
- Clinical trials associations
- Organization details
- Research terms and categories

### Key Features

- **Complete Field Coverage**: Captures ALL fields from the NIH RePORTER API v2 (100+ fields)
- **Incremental Updates**: Upsert logic for efficient updates
- **Scalable Architecture**: Processes millions of records using AWS Glue and Iceberg
- **Star Schema Design**: Normalized dimension and fact tables for efficient querying
- **Automated Scheduling**: Weekly updates via EventBridge
- **Error Handling**: Comprehensive retry logic and error handling

## Architecture

### Pipeline Components

```
┌─────────────────┐
│  EventBridge    │  Weekly Schedule (Sundays 2 AM UTC)
│   Scheduler     │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Step Functions  │  Orchestrates entire pipeline
│  State Machine  │
└────────┬────────┘
         │
         v
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     Lambda      │────>│   Glue Bronze    │────>│   Glue Silver    │
│  API Ingestion  │     │  Raw to Iceberg  │     │  Normalization   │
└─────────────────┘     └──────────────────┘     └──────────────────┘
         │                       │                         │
         v                       v                         v
    Landing Zone              Bronze Zone             Silver Zone
   (Raw JSONL)              (Iceberg Raw)        (Iceberg Star Schema)
```

### Infrastructure

- **Lambda Function**: Queries NIH RePORTER API, handles pagination and rate limiting
- **Glue Bronze Job**: Reads JSONL, writes to Iceberg (preserves raw structure)
- **Glue Silver Job**: Transforms into normalized star schema with 10 tables
- **Step Functions**: Orchestrates Lambda → Bronze → Silver workflow
- **EventBridge**: Schedules weekly pipeline execution
- **S3 Buckets**: Landing zone, bronze, and silver data lakes
- **Glue Data Catalog**: Metadata and schema management

## Data Sources

### NIH RePORTER API v2

- **Base URL**: https://api.reporter.nih.gov
- **Endpoint**: POST /v2/projects/search
- **Rate Limit**: 1 request/second
- **Pagination**: Max 500 records/request, max offset 14,999
- **Documentation**: [NIH RePORTER API Docs](https://api.reporter.nih.gov/)

### API Field Coverage

The pipeline captures **ALL** available fields from the API. See [docs/api_fields_mapping.md](docs/api_fields_mapping.md) for complete field inventory organized by category:

1. **Project Identifiers** (15+ fields): project_num, appl_id, fiscal_year, etc.
2. **Textual Content** (5 fields): abstract, public health relevance, terms
3. **Organization Information** (12 fields): name, location, DUNS, UEI
4. **Personnel** (10+ fields): PIs, program officers, contact info
5. **Funding & Budget** (8 fields): award amounts, direct/indirect costs
6. **Study Section & Review** (6 fields): SRG codes, study section info
7. **NIH Institutes/Centers** (3 fields per IC): code, abbreviation, name
8. **Publications** (2 fields): PMID, PMC ID
9. **Clinical Trials** (1 field): NCT ID
10. **Spending Categories** (1+ fields): NIH research categories

## Schema Design

### Silver Layer Tables

#### Dimension Tables

**dim_nih_projects** (Primary project dimension)
- **Primary Key**: (project_num, fiscal_year)
- **Attributes**: Title, dates, abstract, PI name, activity code
- **Purpose**: Core project information

**dim_nih_organizations** (Organizations/institutions)
- **Primary Key**: org_key (hash of name+city+state)
- **Attributes**: Name, location, DUNS, UEI, department type
- **Purpose**: Organization master data

**dim_nih_personnel** (PIs and Program Officers)
- **Primary Key**: personnel_key
- **Attributes**: Name, profile_id, role (PI/PO), contact PI flag
- **Purpose**: Personnel master data

**dim_nih_study_sections** (Study sections)
- **Primary Key**: study_section_key
- **Attributes**: SRG codes, study section name
- **Purpose**: Review group information

**dim_nih_agencies** (NIH Institutes/Centers)
- **Primary Key**: agency_key
- **Attributes**: IC code, abbreviation, name, type (admin/funding)
- **Purpose**: NIH IC master data

#### Fact Tables

**fact_nih_funding** (Funding events - main fact table)
- **Primary Key**: (project_num, fiscal_year)
- **Foreign Keys**: org_key, admin_ic_key
- **Measures**: award_amount, direct_cost_amt, indirect_cost_amt, total_cost
- **Attributes**: Budget dates, award type, ARRA flag, CFDA code

#### Bridge Tables (Many-to-Many Relationships)

- **bridge_nih_publications**: Links projects to PubMed publications
- **bridge_nih_clinical_trials**: Links projects to clinical trials
- **bridge_nih_spending_categories**: Links projects to spending categories
- **bridge_nih_terms**: Links projects to research terms

### Data Lineage

```
Raw API JSON (Landing)
    └─> Bronze Layer (Complete raw data preserved as JSON + key fields)
        └─> Silver Layer (Normalized star schema with 10 tables)
```

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+ (for CDK)
- AWS CLI configured
- AWS CDK installed (`npm install -g aws-cdk`)

### Setup

```bash
# Clone repository
cd data-pipelines/allsci-data-pipelines/nih_reporter

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make install-dev

# Bootstrap CDK (first time only)
make bootstrap ENV=dev
```

## Deployment

### Deploy to Development

```bash
# Upload Glue scripts and deploy stack
make deploy ENV=dev
```

### Deploy to Production

```bash
# Deploy to production
make deploy ENV=prod
```

### What Gets Deployed

- Lambda function: `nih-reporter-ingestion-{ENV}`
- Glue bronze job: `nih-reporter-bronze-{ENV}`
- Glue silver job: `nih-reporter-silver-{ENV}`
- Step Functions: `nih-reporter-pipeline-{ENV}`
- EventBridge rule: `nih-reporter-weekly-schedule-{ENV}`
- IAM roles and policies
- CloudWatch log groups

## Usage

### Automated Execution

The pipeline runs automatically **every Sunday at 2:00 AM UTC**, processing the last 2 fiscal years.

### Manual Execution

#### Trigger Entire Pipeline

```bash
make trigger-pipeline ENV=dev
```

#### Trigger Individual Components

```bash
# Lambda only (API ingestion)
make trigger-lambda ENV=dev

# Bronze Glue job only
make trigger-bronze ENV=dev

# Silver Glue job only
make trigger-silver ENV=dev
```

#### Custom Fiscal Year Range

```bash
# Via AWS CLI
aws stepfunctions start-execution \
  --state-machine-arn <ARN> \
  --input '{"fiscal_years": [2024, 2023, 2022], "fiscal_years_str": "2024,2023,2022"}'
```

### Monitor Execution

```bash
# Check Lambda logs
aws logs tail /aws/lambda/nih-reporter-ingestion-dev --follow

# Check Glue job status
aws glue get-job-runs --job-name nih-reporter-bronze-dev --max-results 5

# Check Step Functions execution
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --max-results 5
```

## Query Examples

### Using Athena

Connect to the Glue Data Catalog and query using Athena:

#### Basic Project Counts

```sql
-- Total projects by fiscal year
SELECT fiscal_year, COUNT(*) as project_count
FROM allsci_dev.dim_nih_projects
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;
```

#### Funding Analysis

```sql
-- Top funded organizations in FY2024
SELECT
    o.org_name,
    o.org_state,
    COUNT(DISTINCT f.project_num) as project_count,
    SUM(f.award_amount) as total_funding
FROM allsci_dev.fact_nih_funding f
JOIN allsci_dev.dim_nih_organizations o ON f.org_key = o.org_key
WHERE f.fiscal_year = 2024
GROUP BY o.org_name, o.org_state
ORDER BY total_funding DESC
LIMIT 20;
```

#### PI Analysis with Publications

```sql
-- Top PIs by publication count
SELECT
    p.full_name,
    p.role_type,
    COUNT(DISTINCT proj.project_num) as project_count,
    COUNT(DISTINCT pub.pmid) as publication_count,
    SUM(f.award_amount) as total_funding
FROM allsci_dev.dim_nih_personnel p
JOIN allsci_dev.dim_nih_projects proj
    ON p.project_num = proj.project_num
    AND p.fiscal_year = proj.fiscal_year
JOIN allsci_dev.fact_nih_funding f
    ON proj.project_num = f.project_num
    AND proj.fiscal_year = f.fiscal_year
LEFT JOIN allsci_dev.bridge_nih_publications pub
    ON proj.project_num = pub.project_num
    AND proj.fiscal_year = pub.fiscal_year
WHERE p.fiscal_year = 2024 AND p.role_type = 'PI'
GROUP BY p.full_name, p.role_type
HAVING publication_count > 0
ORDER BY publication_count DESC
LIMIT 50;
```

#### Research Terms Analysis

```sql
-- Most common research terms
SELECT
    t.term_text,
    COUNT(DISTINCT t.project_num) as project_count,
    SUM(f.award_amount) as total_funding
FROM allsci_dev.bridge_nih_terms t
JOIN allsci_dev.fact_nih_funding f
    ON t.project_num = f.project_num
    AND t.fiscal_year = f.fiscal_year
WHERE t.fiscal_year = 2024
GROUP BY t.term_text
ORDER BY project_count DESC
LIMIT 100;
```

#### Institute/Center Funding Distribution

```sql
-- Funding by NIH Institute/Center
SELECT
    a.ic_abbreviation,
    a.ic_name,
    COUNT(DISTINCT f.project_num) as project_count,
    SUM(f.award_amount) as total_awards,
    AVG(f.award_amount) as avg_award
FROM allsci_dev.fact_nih_funding f
JOIN allsci_dev.dim_nih_agencies a ON f.admin_ic_key = a.agency_key
WHERE f.fiscal_year = 2024 AND a.agency_type = 'admin'
GROUP BY a.ic_abbreviation, a.ic_name
ORDER BY total_awards DESC;
```

#### Clinical Trials Linkage

```sql
-- Projects with clinical trials
SELECT
    proj.project_title,
    proj.project_num,
    ct.nct_id,
    f.award_amount
FROM allsci_dev.dim_nih_projects proj
JOIN allsci_dev.bridge_nih_clinical_trials ct
    ON proj.project_num = ct.project_num
    AND proj.fiscal_year = ct.fiscal_year
JOIN allsci_dev.fact_nih_funding f
    ON proj.project_num = f.project_num
    AND proj.fiscal_year = f.fiscal_year
WHERE proj.fiscal_year = 2024
ORDER BY f.award_amount DESC;
```

### Using PySpark (Glue Notebooks)

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .getOrCreate()

# Query projects
projects_df = spark.sql("""
    SELECT * FROM glue_catalog.allsci_dev.dim_nih_projects
    WHERE fiscal_year = 2024
""")

projects_df.show()
```

## Development

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_lambda_handler.py -v

# Run with coverage
pytest --cov=nih_reporter --cov-report=html
```

### Code Quality

```bash
# Linting
make lint

# Formatting
make format

# Type checking
mypy nih_reporter/
```

### Local Development

```bash
# Install in development mode
pip install -e .

# Run Jupyter for exploration
jupyter notebook docs/api_exploration.ipynb
```

## Troubleshooting

### Common Issues

**Lambda Timeout**
- Increase timeout in `nih_reporter_stack.py` (currently 15 minutes)
- Process fewer fiscal years per execution

**Glue Job Fails with OOM**
- Increase worker count or worker type (currently G.2X with 20 workers for silver)
- Check for data skew in partitions

**API Rate Limiting**
- Default delay is 1 second between requests
- Increase `RATE_LIMIT_DELAY` environment variable if needed

**Missing Data in Silver Layer**
- Check bronze layer: `make query-bronze ENV=dev`
- Review Glue job logs in CloudWatch
- Verify fiscal_years parameter passed correctly

**Iceberg Table Not Found**
- Ensure Glue database exists
- Check table location in S3
- Verify Glue Data Catalog permissions

### Viewing Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/nih-reporter-ingestion-dev --follow

# Glue job logs
aws logs tail /aws-glue/jobs/output --follow --filter-pattern "nih-reporter-bronze-dev"

# Step Functions logs
aws logs tail /aws/vendedlogs/states/nih-reporter-dev --follow
```

## Update Frequency

- **Scheduled**: Weekly on Sundays at 2:00 AM UTC
- **Incremental**: Processes last 2 fiscal years by default
- **Backfill**: Can be run for any fiscal year range on demand

## Data Retention

- **Landing Zone**: Raw JSONL files retained indefinitely
- **Bronze Layer**: Complete raw data retained indefinitely (Iceberg snapshots)
- **Silver Layer**: Current data with full update history via Iceberg time travel

## Performance

- **API Ingestion**: ~1,000 records/minute (rate limited)
- **Bronze Processing**: ~100,000 records/minute
- **Silver Processing**: ~50,000 records/minute
- **Typical Runtime**: 2-4 hours for 2 fiscal years (~500K projects)

## Cost Optimization

- Bronze and Silver jobs only run after Lambda confirms new data
- Incremental upserts minimize reprocessing
- Iceberg format reduces storage costs via compression
- Scheduled during off-peak hours

## Security

- IAM roles follow least-privilege principle
- S3 buckets require server-side encryption
- VPC endpoints recommended for production
- No API keys required (NIH RePORTER is public)

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and test: `make test lint`
3. Update documentation
4. Submit pull request

## Support

- **API Issues**: [NIH RePORTER Support](https://report.nih.gov/contact-us)
- **Pipeline Issues**: Create GitHub issue
- **AWS Issues**: Check CloudWatch logs

## License

Internal use only - AllSci Data Pipelines

## References

- [NIH RePORTER Website](https://reporter.nih.gov/)
- [NIH RePORTER API Documentation](https://api.reporter.nih.gov/)
- [API Field Mapping](docs/api_fields_mapping.md)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
