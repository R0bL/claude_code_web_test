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
- **3-Layer Architecture**: Landing → Bronze → Silver following AllSci standards
- **Source-Specific Tables**: Silver layer with 11 normalized source tables
- **Automated Scheduling**: Weekly updates via EventBridge
- **Error Handling**: Comprehensive retry logic and error handling

## Architecture

The NIH Reporter pipeline follows AllSci's standardized modular architecture with convention-based configuration and shared utilities.

### Architecture Alignment

This pipeline has been refactored to align with AllSci's architectural standards, addressing:

1. **Modular CDK Constructs**: Separated into reusable constructs (Glue, Lambda, Step Functions, EventBridge)
2. **Shared IAM Roles**: References `allsci-{ENV}-glue-default-service-role` (no new role creation)
3. **Complete Package Structure**: Includes shared utilities (lake_tools, opensearch, postgresql, utils)
4. **Glue 5.0**: Uses latest Glue version for performance and features
5. **Job Bookmarks**: Enabled for incremental processing and preventing reprocessing
6. **VPC Connections**: Configured with `allsci-{ENV}-network` for private resource access
7. **Lambda Layers**: Packages dependencies in layer.zip for efficient deployments
8. **Auto-scaling**: Enabled on Glue jobs for cost optimization
9. **Standard Script Locations**: Uses AWS Glue assets bucket with consistent paths
10. **Convention-based Configuration**: Environment-driven naming (ENV parameter only)

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
   (Raw JSONL)          (Iceberg data_object)   (11 Source Tables)
```

### Infrastructure

- **Lambda Function**: Queries NIH RePORTER API, handles pagination and rate limiting
- **Glue Bronze Job**: Reads JSONL, writes to Iceberg (preserves raw JSON structure)
- **Glue Silver Job**: Transforms into 11 normalized source-specific tables
- **Step Functions**: Orchestrates Lambda → Bronze → Silver workflow
- **EventBridge**: Schedules weekly pipeline execution
- **S3 Buckets**: Landing zone, bronze, and silver data lakes
- **Glue Data Catalog**: Metadata and schema management

### Database Structure

Following AllSci's 3-layer architecture:

- **Bronze Database**: `allsci_{ENV}_nih_reporter_bronze`
  - Table: `projects_metadata` (raw JSON data)
- **Silver Database**: `allsci_{ENV}_nih_reporter_silver`
  - 11 source-specific tables (see Schema Design below)
- **Gold Layer**: Future work - dimensional model combining multiple grant sources

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

### Bronze Layer

**Database**: `allsci_{ENV}_nih_reporter_bronze`

**projects_metadata** (Raw data table)
- `project_num` (STRING): Project/grant number (natural key)
- `fiscal_year` (INT): Fiscal year (partition key)
- `data_object` (STRING): Complete raw JSON from API
- `source_date` (DATE): Date when data was extracted
- `ingestion_datetime` (TIMESTAMP): When ingested to bronze

### Silver Layer Tables

**Database**: `allsci_{ENV}_nih_reporter_silver`

Silver layer contains 11 source-specific tables that flatten and normalize the NIH Reporter API data. All tables use natural keys (project_num + fiscal_year) for relationships.

#### Core Project Table

**nih_reporter_projects** (Main project data)
- **Natural Keys**: project_num, fiscal_year
- **Attributes**: Project title, dates, abstract, public health relevance, activity code, funding amounts, CFDA code
- **Partition**: fiscal_year

#### Related Entity Tables

**nih_reporter_organizations** (Organization details)
- **Natural Keys**: org_key (md5 hash), project_num, fiscal_year
- **Attributes**: Organization name, location, DUNS, UEI, FIPS code

**nih_reporter_principal_investigators** (PIs, exploded from array)
- **Natural Keys**: project_num, fiscal_year, profile_id
- **Attributes**: Name fields, is_contact_pi flag
- **Partition**: fiscal_year

**nih_reporter_program_officers** (Program officers, exploded from array)
- **Natural Keys**: project_num, fiscal_year, full_name
- **Attributes**: Name fields
- **Partition**: fiscal_year

**nih_reporter_publications** (Publications, exploded from array)
- **Natural Keys**: project_num, fiscal_year, pmid
- **Attributes**: PMID, PMC ID
- **Partition**: fiscal_year

**nih_reporter_clinical_trials** (Clinical trials, exploded from array)
- **Natural Keys**: project_num, fiscal_year, nct_id
- **Attributes**: NCT ID
- **Partition**: fiscal_year

**nih_reporter_agencies_admin** (Admin IC)
- **Natural Keys**: project_num, fiscal_year
- **Attributes**: IC code, abbreviation, name
- **Partition**: fiscal_year

**nih_reporter_agencies_funding** (Funding ICs, exploded from array)
- **Natural Keys**: project_num, fiscal_year, ic_code
- **Attributes**: IC code, abbreviation, name
- **Partition**: fiscal_year

**nih_reporter_spending_categories** (Spending categories, exploded from array)
- **Natural Keys**: project_num, fiscal_year, category_name
- **Attributes**: Category name
- **Partition**: fiscal_year

**nih_reporter_terms** (Research terms, exploded from array)
- **Natural Keys**: project_num, fiscal_year, term_text
- **Attributes**: Term text
- **Partition**: fiscal_year

**nih_reporter_study_sections** (Study section details)
- **Natural Keys**: project_num, fiscal_year
- **Attributes**: SRG codes, study section name
- **Partition**: fiscal_year

### Data Lineage

```
Landing Zone (Raw JSONL with source_date)
    └─> Bronze Layer (project_num, fiscal_year, data_object, source_date)
        └─> Silver Layer (11 normalized source tables with natural keys)
            └─> Gold Layer (Future: dimensional model with AllSci IDs)
```

### Notes on Architecture

- **Silver = Source Tables**: Silver layer preserves NIH Reporter-specific structure with natural keys
- **No AllSci IDs in Silver**: AllSci standardized IDs (ASC-GR-*) will be generated in Gold layer
- **Gold Layer (Future)**: Will combine NIH Reporter with other grant sources (NSF, private foundations) into unified dimensional model with `dim_grant` and `fact_grant_funding` tables

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

The deployment creates a modular infrastructure using separate CDK constructs:

- **Lambda Function**: `{ENV}_allsci_nih_reporter_trigger`
  - Python 3.11 runtime with Lambda layer
  - 15-minute timeout, 1024 MB memory
  - 5 concurrent executions max
- **Glue Jobs**: 
  - Bronze: `{ENV}_nih_reporter_bronze` (Glue 5.0, G.1X workers, VPC-enabled)
  - Silver: `{ENV}_nih_reporter_silver` (Glue 5.0, G.1X workers, VPC-enabled)
  - Both use shared IAM role: `allsci-{ENV}-glue-default-service-role`
  - Job bookmarks enabled for incremental processing
- **Step Functions**: `nih-reporter-pipeline-{ENV}` (orchestrates Lambda → Bronze → Silver)
- **EventBridge**: `nih-reporter-weekly-{ENV}` (Sunday 2 AM UTC schedule)
- **CloudWatch Log Groups**: `/aws/vendedlogs/states/nih-reporter-{ENV}`

All resources follow AllSci naming conventions and reuse shared infrastructure.

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

Connect to the Glue Data Catalog and query using Athena. Note that queries use the **Silver layer** database with source-specific tables.

#### Basic Project Counts

```sql
-- Total projects by fiscal year
SELECT fiscal_year, COUNT(*) as project_count
FROM allsci_dev_nih_reporter_silver.nih_reporter_projects
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;
```

#### Funding Analysis

```sql
-- Top funded organizations in FY2024
SELECT
    o.org_name,
    o.org_state,
    o.org_city,
    COUNT(DISTINCT p.project_num) as project_count,
    SUM(p.award_amount) as total_funding,
    AVG(p.award_amount) as avg_award
FROM allsci_dev_nih_reporter_silver.nih_reporter_projects p
JOIN allsci_dev_nih_reporter_silver.nih_reporter_organizations o 
    ON p.project_num = o.project_num 
    AND p.fiscal_year = o.fiscal_year
WHERE p.fiscal_year = 2024
GROUP BY o.org_name, o.org_state, o.org_city
ORDER BY total_funding DESC
LIMIT 20;
```

#### PI Analysis with Publications

```sql
-- Top PIs by publication count
SELECT
    pi.full_name,
    pi.is_contact_pi,
    COUNT(DISTINCT p.project_num) as project_count,
    COUNT(DISTINCT pub.pmid) as publication_count,
    SUM(p.award_amount) as total_funding
FROM allsci_dev_nih_reporter_silver.nih_reporter_principal_investigators pi
JOIN allsci_dev_nih_reporter_silver.nih_reporter_projects p
    ON pi.project_num = p.project_num
    AND pi.fiscal_year = p.fiscal_year
LEFT JOIN allsci_dev_nih_reporter_silver.nih_reporter_publications pub
    ON p.project_num = pub.project_num
    AND p.fiscal_year = pub.fiscal_year
WHERE pi.fiscal_year = 2024
GROUP BY pi.full_name, pi.is_contact_pi
HAVING publication_count > 0
ORDER BY publication_count DESC
LIMIT 50;
```

#### Research Terms Analysis

```sql
-- Most common research terms
SELECT
    t.term_text,
    COUNT(DISTINCT p.project_num) as project_count,
    SUM(p.award_amount) as total_funding
FROM allsci_dev_nih_reporter_silver.nih_reporter_terms t
JOIN allsci_dev_nih_reporter_silver.nih_reporter_projects p
    ON t.project_num = p.project_num
    AND t.fiscal_year = p.fiscal_year
WHERE t.fiscal_year = 2024
GROUP BY t.term_text
ORDER BY project_count DESC
LIMIT 100;
```

#### Institute/Center Funding Distribution

```sql
-- Funding by NIH Institute/Center (Admin IC)
SELECT
    a.ic_abbreviation,
    a.ic_name,
    COUNT(DISTINCT p.project_num) as project_count,
    SUM(p.award_amount) as total_awards,
    AVG(p.award_amount) as avg_award
FROM allsci_dev_nih_reporter_silver.nih_reporter_agencies_admin a
JOIN allsci_dev_nih_reporter_silver.nih_reporter_projects p
    ON a.project_num = p.project_num
    AND a.fiscal_year = p.fiscal_year
WHERE a.fiscal_year = 2024
GROUP BY a.ic_abbreviation, a.ic_name
ORDER BY total_awards DESC;
```

#### Clinical Trials Linkage

```sql
-- Projects with clinical trials
SELECT
    p.project_title,
    p.project_num,
    ct.nct_id,
    p.award_amount
FROM allsci_dev_nih_reporter_silver.nih_reporter_projects p
JOIN allsci_dev_nih_reporter_silver.nih_reporter_clinical_trials ct
    ON p.project_num = ct.project_num
    AND p.fiscal_year = ct.fiscal_year
WHERE p.fiscal_year = 2024
ORDER BY p.award_amount DESC
LIMIT 100;
```

### Using PySpark (Glue Notebooks)

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    .getOrCreate()

# Query projects from Silver layer
projects_df = spark.sql("""
    SELECT * 
    FROM glue_catalog.allsci_dev_nih_reporter_silver.nih_reporter_projects
    WHERE fiscal_year = 2024
""")

# Join with organizations
projects_with_orgs = spark.sql("""
    SELECT p.*, o.org_name, o.org_city, o.org_state
    FROM glue_catalog.allsci_dev_nih_reporter_silver.nih_reporter_projects p
    JOIN glue_catalog.allsci_dev_nih_reporter_silver.nih_reporter_organizations o
        ON p.project_num = o.project_num AND p.fiscal_year = o.fiscal_year
    WHERE p.fiscal_year = 2024
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
