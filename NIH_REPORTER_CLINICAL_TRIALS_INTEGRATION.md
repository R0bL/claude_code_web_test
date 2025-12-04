# NIH Reporter → Clinical Trials Integration Guide (CORRECTED)

## Executive Summary

**CORRECTION**: The NIH Reporter Projects API **does NOT directly provide** clinical trials data in the project responses. Instead, the link between NIH-funded projects and clinical trials comes from a **separate data source: NIH ExPORTER Clinical Studies files**.

This document explains:
1. Why the `clinical_trials` field in your pipeline code may not work
2. The correct approach using NIH ExPORTER Clinical Studies downloads
3. How to build a pipeline that links projects to clinical trials via `core_project_num`

---

## Problem: The `clinical_trials` Field May Not Exist

### Current Pipeline Code Assumption

Your pipeline includes a `NihReporterClinicalTrials` transformation class (lines 391-433 in `transformations.py`) that expects:

```python
{
  "project_num": "5R01CA123456-05",
  "fiscal_year": 2024,
  "clinical_trials": [
    {"nct_id": "NCT04267848"}  # ← This field may not exist in API response
  ]
}
```

### Reality Check

After investigating the NIH Reporter API v2, the `clinical_trials` array field **may not be present** in the Projects API response. The pipeline code was likely built with the expectation that this field would be available, but it appears this data is provided through a **different mechanism**.

---

## The Correct Approach: NIH ExPORTER Clinical Studies Files

### How the Linkage Actually Works

1. **Investigators enter grant numbers** when registering trials on ClinicalTrials.gov
2. **ClinicalTrials.gov provides a feed** to NIH with grant numbers → NCT ID mappings
3. **NIH ExPORTER** publishes this linkage data as **bulk CSV files**
4. The linkage uses **`CORE_PROJECT_NUM`** (not `project_num`)

### Data Flow Diagram

```
ClinicalTrials.gov (NCT entries with NIH grant numbers)
    ↓
  Feed to NIH
    ↓
NIH ExPORTER Clinical Studies CSV
    ├─ CORE_PROJECT_NUM
    └─ NCT_ID (or similar field name)
    ↓
  Join with NIH Reporter Projects
    (on core_project_num)
    ↓
  Use NCT_ID to query ClinicalTrials.gov API v2
    ↓
  Detailed Clinical Trial Data
```

---

## NIH ExPORTER Clinical Studies File

### Download Location

**URL**: `https://reporter.nih.gov/exporter` (navigate to Clinical Studies section)

Or programmatically from ExPORTER bulk download endpoints.

### File Format

- **Format**: CSV
- **Update Frequency**: Weekly (typically)
- **Size**: Varies (likely 10-50 MB)

### Expected Schema

Based on NIH documentation, the Clinical Studies CSV file contains at minimum:

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| `CORE_PROJECT_NUM` | String | Core project number (links to NIH projects) |
| `CLINICALTRIALS_GOV_ID` or `NCT_ID` | String | ClinicalTrials.gov NCT identifier |
| Additional fields... | Various | May include study title, status, etc. |

**Important Notes**:
- Clinical Studies are associated with projects but **cannot be identified with any particular year** or fiscal year
- Linkages come directly from ClinicalTrials.gov where grant numbers are entered during trial registration
- The join key is `CORE_PROJECT_NUM`, not `project_num`

---

## Proposed Pipeline Architecture

### Option 1: Separate ExPORTER Clinical Studies Pipeline

Create a new pipeline that:
1. Downloads the NIH ExPORTER Clinical Studies CSV file
2. Processes it into a linkage table
3. Joins with existing NIH Reporter projects
4. Uses NCT IDs to enrich with ClinicalTrials.gov data

```
┌─────────────────────────────────────────────────────────────┐
│         ExPORTER Clinical Studies Pipeline                  │
├─────────────────────────────────────────────────────────────┤
│  EventBridge Trigger (Weekly)                                │
│    ↓                                                         │
│  Lambda: Download ExPORTER CSV                               │
│    ├─ URL: reporter.nih.gov/exporter                        │
│    ├─ Download CLINICAL_STUDIES.csv                         │
│    └─ Save to S3 Landing Zone                               │
│    ↓                                                         │
│  Glue Bronze Job                                             │
│    ├─ Read CSV from landing zone                            │
│    ├─ Store raw data in Bronze                              │
│    └─ Deduplicate on (core_project_num, nct_id)            │
│    ↓                                                         │
│  Glue Silver Job                                             │
│    ├─ Create linkage table: exporter_clinical_studies       │
│    │  Schema: (core_project_num, nct_id, source_date)       │
│    └─ Upsert to Iceberg table                               │
│    ↓                                                         │
│  Glue Clinical Trials Enrichment Job                         │
│    ├─ Read unique NCT IDs                                   │
│    ├─ Query ClinicalTrials.gov API (batch mode)            │
│    ├─ Rate limit: 50 req/min                                │
│    └─ Create detailed clinical trials tables                │
└─────────────────────────────────────────────────────────────┘
```

### Lambda Function: Download ExPORTER CSV

```python
import boto3
import requests
from datetime import datetime

LANDING_ZONE_BUCKET = os.environ['LANDING_ZONE_BUCKET']
EXPORTER_URL = 'https://reporter.nih.gov/exporter/clinicalstudies/download'

def lambda_handler(event, context):
    """
    Download NIH ExPORTER Clinical Studies CSV file.
    """
    # Download CSV
    response = requests.get(EXPORTER_URL, stream=True, timeout=300)
    response.raise_for_status()

    # Generate S3 key
    source_date = datetime.utcnow().strftime('%Y-%m-%d')
    s3_key = f"exporter_clinical_studies/clinical_studies_{source_date}.csv"

    # Upload to S3
    s3_client = boto3.client('s3')
    s3_client.put_object(
        Bucket=LANDING_ZONE_BUCKET,
        Key=s3_key,
        Body=response.content,
        ContentType='text/csv',
        Metadata={
            'source_date': source_date,
            'source_url': EXPORTER_URL,
            'ingestion_timestamp': datetime.utcnow().isoformat()
        }
    )

    return {
        'status': 'success',
        's3_path': f"s3://{LANDING_ZONE_BUCKET}/{s3_key}",
        'source_date': source_date
    }
```

### Bronze Glue Job

```python
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from pyspark.sql import functions as F

# Read CSV from landing zone
df_raw = spark.read.option("header", "true").csv(
    f"s3://{LANDING_ZONE_BUCKET}/exporter_clinical_studies/*.csv"
)

# Add metadata
df_bronze = df_raw.withColumn(
    "ingestion_datetime", F.current_timestamp()
).withColumn(
    "source_date", F.current_date()
)

# Write to Bronze Iceberg table
df_bronze.writeTo(f"{BRONZE_DATABASE}.exporter_clinical_studies") \
    .using("iceberg") \
    .tableProperty("write.format.default", "parquet") \
    .tableProperty("write.parquet.compression-codec", "zstd") \
    .createOrReplace()
```

### Silver Layer Linkage Table

```python
# Read from Bronze
df_bronze = spark.read.table(f"{BRONZE_DATABASE}.exporter_clinical_studies")

# Transform and deduplicate
df_silver = df_bronze.select(
    F.col("CORE_PROJECT_NUM").alias("core_project_num"),
    F.col("CLINICALTRIALS_GOV_ID").alias("nct_id"),  # Adjust field name as needed
    F.col("source_date"),
    F.col("ingestion_datetime")
).filter(
    F.col("core_project_num").isNotNull() &
    F.col("nct_id").isNotNull()
).dropDuplicates(["core_project_num", "nct_id"])

# Create temp view for MERGE
df_silver.createOrReplaceTempView("upsert_batch")

# MERGE INTO silver table
spark.sql(f"""
    MERGE INTO {SILVER_DATABASE}.exporter_clinical_studies AS target
    USING upsert_batch AS source
    ON target.core_project_num = source.core_project_num
       AND target.nct_id = source.nct_id
    WHEN MATCHED AND source.source_date > target.source_date THEN
        UPDATE SET *
    WHEN NOT MATCHED THEN
        INSERT *
""")
```

### Silver Layer Table Schema

```sql
CREATE TABLE exporter_clinical_studies (
    core_project_num STRING,
    nct_id STRING,
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
PARTITIONED BY (months(source_date))
TBLPROPERTIES (
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd'
)
```

---

## Joining NIH Reporter Projects with Clinical Trials

### SQL Query Example

```sql
-- Get NIH projects with their associated clinical trials
SELECT
    p.project_num,
    p.core_project_num,
    p.project_title,
    p.fiscal_year,
    p.award_amount,
    org.org_name,
    org.org_state,
    cs.nct_id,
    ct.brief_title AS trial_title,
    ct.overall_status AS trial_status,
    ct.phase AS trial_phase,
    ct.enrollment_count,
    ct.start_date AS trial_start_date,
    ct.lead_sponsor_name
FROM
    allsci_silver_prod.nih_reporter_projects p
    -- Join with ExPORTER Clinical Studies linkage table
    INNER JOIN allsci_silver_prod.exporter_clinical_studies cs
        ON p.core_project_num = cs.core_project_num
    -- Join with enriched clinical trials data
    LEFT JOIN allsci_silver_prod.clinical_trials_studies ct
        ON cs.nct_id = ct.nct_id
    -- Join with organization info
    LEFT JOIN allsci_silver_prod.nih_reporter_organizations org
        ON p.project_num = org.project_num
WHERE
    p.fiscal_year >= 2023
    AND ct.overall_status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'ENROLLING_BY_INVITATION')
ORDER BY
    p.award_amount DESC
LIMIT 100;
```

### Important Note About the Join Key

**Use `core_project_num`, NOT `project_num`**:
- `core_project_num` is the base grant identifier (e.g., `R01CA123456`)
- `project_num` includes suffixes for specific years (e.g., `5R01CA123456-05`)
- ExPORTER Clinical Studies links on `core_project_num` because trials span multiple years

---

## Implementation Steps

### Phase 1: Verify ExPORTER Access
```bash
# Test downloading the ExPORTER Clinical Studies file
curl -O "https://reporter.nih.gov/exporter/clinicalstudies/download"

# Examine the file structure
head -20 clinical_studies.csv
```

### Phase 2: Understand the Schema
- Open the downloaded CSV
- Identify exact field names (they may vary from documentation)
- Note: Field names might be different than expected:
  - `CORE_PROJECT_NUM` vs `Core_Project_Num`
  - `NCT_ID` vs `CLINICALTRIALS_GOV_ID` vs `ClinicalTrials_gov_ID`

### Phase 3: Validate Linkage Coverage
```sql
-- Count how many NIH projects have clinical trials
SELECT
    COUNT(DISTINCT p.core_project_num) AS total_projects,
    COUNT(DISTINCT cs.core_project_num) AS projects_with_trials,
    ROUND(COUNT(DISTINCT cs.core_project_num) * 100.0 / COUNT(DISTINCT p.core_project_num), 2) AS coverage_pct
FROM
    allsci_silver_prod.nih_reporter_projects p
    LEFT JOIN allsci_silver_prod.exporter_clinical_studies cs
        ON p.core_project_num = cs.core_project_num;
```

### Phase 4: Build Pipeline
1. Create Lambda for ExPORTER CSV download
2. Create Bronze Glue job
3. Create Silver Glue job for linkage table
4. Test with sample data
5. Full historical load
6. Schedule weekly updates

### Phase 5: Enrich with ClinicalTrials.gov API
- Use NCT IDs from linkage table
- Query ClinicalTrials.gov API v2
- Build detailed clinical trials tables (see original doc for API details)

---

## Fixing Your Current Pipeline Code

### Option A: Remove the Clinical Trials Transformer (Recommended)

Since the `clinical_trials` field doesn't exist in the Projects API, remove it from the pipeline:

**File**: `nih_reporter/glue/package/lake_tools/catalogs.py`

```python
class TransformationCatalog(Catalog):
    def __init__(self):
        super().__init__()
        self.catalog = {
            "nih_reporter_projects": NihReporterProjects,
            "nih_reporter_organizations": NihReporterOrganizations,
            "nih_reporter_principal_investigators": NihReporterPrincipalInvestigators,
            "nih_reporter_program_officers": NihReporterProgramOfficers,
            "nih_reporter_publications": NihReporterPublications,
            # "nih_reporter_clinical_trials": NihReporterClinicalTrials,  # ← REMOVE THIS
            "nih_reporter_agencies_admin": NihReporterAgenciesAdmin,
            "nih_reporter_agencies_funding": NihReporterAgenciesFunding,
            "nih_reporter_spending_categories": NihReporterSpendingCategories,
            "nih_reporter_terms": NihReporterTerms,
            "nih_reporter_study_sections": NihReporterStudySections,
        }
```

**File**: `nih_reporter/glue/jobs/nih_reporter_silver.py`

```python
# Process each silver table using TransformationCatalog
for table in (
    "nih_reporter_projects",
    "nih_reporter_organizations",
    "nih_reporter_principal_investigators",
    "nih_reporter_program_officers",
    "nih_reporter_publications",
    # "nih_reporter_clinical_trials",  # ← REMOVE THIS
    "nih_reporter_agencies_admin",
    "nih_reporter_agencies_funding",
    "nih_reporter_spending_categories",
    "nih_reporter_terms",
    "nih_reporter_study_sections",
):
    # ... processing code
```

### Option B: Test If Field Exists

Add logic to check if the field actually exists in the API response:

```python
# In the Lambda handler, check a sample response
sample_response = query_api({"criteria": {"fiscal_years": [2024]}, "limit": 1})
if sample_response['results']:
    sample_project = sample_response['results'][0]
    if 'clinical_trials' in sample_project:
        logger.info("✓ clinical_trials field exists in API response")
    else:
        logger.warning("✗ clinical_trials field NOT found in API response")
        logger.info("Available fields: " + ", ".join(sample_project.keys()))
```

---

## Data Dictionary References

### NIH ExPORTER
- **Main Page**: https://reporter.nih.gov/exporter
- **Data Dictionary**: https://report.nih.gov/exporter-data-dictionary
- **FAQ**: https://exporter.nih.gov/faq.aspx

### ClinicalTrials.gov API
- **API Documentation**: https://clinicaltrials.gov/data-api/api
- **API v2 Release Notes**: https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html

### NIH Reporter
- **Projects API**: https://api.reporter.nih.gov/
- **Data Elements PDF**: https://api.reporter.nih.gov/documents/Data%20Elements%20for%20RePORTER%20Project%20API_V2.pdf

---

## Key Differences from Original Document

| Original Assumption | Corrected Understanding |
|---------------------|-------------------------|
| `clinical_trials` field in Projects API | Field may not exist; use ExPORTER instead |
| Join on `project_num` | Join on `core_project_num` |
| Data embedded in project responses | Data in separate ExPORTER CSV file |
| Query API for each project | Download bulk CSV file weekly |
| Linkage by fiscal year | Linkage **not** tied to specific year |

---

## Recommended Next Steps

1. **Download a sample ExPORTER Clinical Studies CSV** to examine the actual schema
2. **Check your current pipeline** to see if `nih_reporter_clinical_trials` table has any data
3. **Build the ExPORTER Clinical Studies pipeline** following the architecture above
4. **Verify linkage quality** by joining on `core_project_num`
5. **Enrich with ClinicalTrials.gov API** to get detailed trial information

---

## References & Sources

### NIH ExPORTER
- [NIH ExPORTER Main Page](https://reporter.nih.gov/exporter)
- [ExPORTER Data Dictionary](https://report.nih.gov/exporter-data-dictionary)
- [ExPORTER FAQ](https://exporter.nih.gov/faq.aspx)
- [Federal RePORTER File Download](https://federalreporter.nih.gov/FileDownload)

### Documentation
- [NIH RePORTER FAQ about Clinical Studies](https://report.nih.gov/faqs)
- [GitHub: rnabioco/nihexporter R Package](https://github.com/rnabioco/nihexporter)
- [GitHub: nih_project_data Analysis](https://github.com/mrtoronto/nih_project_data)

### ClinicalTrials.gov
- [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api)
- [NLM Technical Bulletin on API v2](https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html)

---

**Document Version**: 2.0 (CORRECTED)
**Last Updated**: 2025-12-04
**Author**: Claude Code
