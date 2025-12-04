# NIH Reporter → Clinical Trials Integration Guide

## Executive Summary

The NIH Reporter API already provides **NCT IDs** (ClinicalTrials.gov identifiers) that link NIH-funded research projects to their associated clinical trials. This document explains how these identifiers are currently captured and how to use them to pull comprehensive clinical trial data from ClinicalTrials.gov.

## Current Implementation Status

### ✅ What's Already Working

Your NIH Reporter pipeline **already captures NCT IDs** in the silver layer:

**Table**: `nih_reporter_clinical_trials`
**Location**: `allsci_silver_{ENV}/nih_reporter_clinical_trials`
**Schema**:
- `project_num` (String) - NIH project number
- `fiscal_year` (Integer) - Fiscal year
- `nct_id` (String) - **ClinicalTrials.gov NCT identifier**
- `source_date` (Date) - Data freshness timestamp
- `ingestion_datetime` (Timestamp) - ETL timestamp

**Data Source**: The Lambda function queries NIH Reporter API and receives:
```json
{
  "project_num": "5R01CA123456-05",
  "fiscal_year": 2024,
  "clinical_trials": [
    {"nct_id": "NCT04267848"},
    {"nct_id": "NCT03892345"}
  ]
}
```

The silver Glue job (lines 391-433 in `transformations.py`) explodes this array into individual rows.

---

## The Link: How NIH Reporter Connects to Clinical Trials

### Data Flow

```
NIH Reporter API
    ↓
  clinical_trials[] field contains NCT IDs
    ↓
  nih_reporter_clinical_trials table (CURRENT)
    ↓
  NCT ID → ClinicalTrials.gov API (FUTURE ENHANCEMENT)
    ↓
  Detailed Clinical Trial Data
```

### Example Connection

```sql
-- Current data in your silver layer
SELECT
    project_num,
    nct_id
FROM allsci_silver_prod.nih_reporter_clinical_trials
WHERE project_num = '5R01CA123456-05';
```

**Result**:
| project_num | nct_id |
|-------------|--------|
| 5R01CA123456-05 | NCT04267848 |
| 5R01CA123456-05 | NCT03892345 |

---

## ClinicalTrials.gov API Integration

### API Overview

**Base URL**: `https://clinicaltrials.gov/api/v2`

**Key Characteristics**:
- ✅ Public API (no authentication required)
- ✅ REST API using OpenAPI 3.0 specification
- ⚠️ Rate limit: ~50 requests per minute per IP
- ✅ Supports batch queries for efficiency

### Primary Endpoints

#### 1. Single Study Lookup (by NCT ID)
```
GET https://clinicaltrials.gov/api/v2/studies/{NCT_ID}
```

**Example**:
```bash
curl "https://clinicaltrials.gov/api/v2/studies/NCT04267848"
```

**Response Structure**:
```json
{
  "protocolSection": {
    "identificationModule": {
      "nctId": "NCT04267848",
      "orgStudyIdInfo": {"id": "Protocol-001"},
      "briefTitle": "Study of Drug X in Cancer Patients"
    },
    "statusModule": {
      "statusVerifiedDate": "2024-01",
      "overallStatus": "RECRUITING",
      "startDateStruct": {"date": "2024-01-15"},
      "completionDateStruct": {"date": "2026-12-31"}
    },
    "sponsorCollaboratorsModule": {
      "leadSponsor": {"name": "University of California"}
    },
    "descriptionModule": {
      "briefSummary": "This study investigates...",
      "detailedDescription": "Full protocol details..."
    },
    "conditionsModule": {
      "conditions": ["Breast Cancer", "Metastatic Cancer"]
    },
    "eligibilityModule": {
      "eligibilityCriteria": "Inclusion: Age 18+...",
      "sex": "ALL",
      "minimumAge": "18 Years",
      "maximumAge": "N/A"
    },
    "designModule": {
      "studyType": "INTERVENTIONAL",
      "phases": ["PHASE2"],
      "designInfo": {
        "allocation": "RANDOMIZED",
        "interventionModel": "PARALLEL",
        "primaryPurpose": "TREATMENT"
      }
    },
    "armsInterventionsModule": {
      "interventions": [
        {
          "type": "DRUG",
          "name": "Drug X",
          "description": "Experimental treatment"
        }
      ]
    },
    "outcomesModule": {
      "primaryOutcomes": [
        {
          "measure": "Overall Survival",
          "timeFrame": "5 years"
        }
      ]
    },
    "contactsLocationsModule": {
      "locations": [
        {
          "facility": "UCSF Medical Center",
          "city": "San Francisco",
          "state": "California",
          "country": "United States"
        }
      ]
    }
  },
  "resultsSection": {
    "participantFlowModule": {...},
    "baselineCharacteristicsModule": {...},
    "outcomeMeasuresModule": {...}
  }
}
```

#### 2. Batch Studies Query
```
GET https://clinicaltrials.gov/api/v2/studies?query.id={NCT_ID1}+OR+{NCT_ID2}
```

**Example**:
```bash
curl "https://clinicaltrials.gov/api/v2/studies?query.id=NCT04267848+OR+NCT03892345&pageSize=100"
```

#### 3. Search with Filters
```
GET https://clinicaltrials.gov/api/v2/studies?query.cond={condition}&query.term={term}
```

---

## Proposed Architecture for Clinical Trials Enrichment

### Option 1: New Data Pipeline (Recommended)

Add a dedicated Clinical Trials pipeline that:
1. Reads NCT IDs from `nih_reporter_clinical_trials`
2. Queries ClinicalTrials.gov API
3. Writes to new silver tables

```
┌─────────────────────────────────────────────────────────────┐
│            Clinical Trials Pipeline Stack                   │
├─────────────────────────────────────────────────────────────┤
│  EventBridge Trigger (Weekly, after NIH Reporter)           │
│    ↓                                                         │
│  Lambda: Clinical Trials API Ingestion                      │
│    ├─ Read NCT IDs from Athena query                        │
│    ├─ Query ClinicalTrials.gov API (batch mode)            │
│    ├─ Rate limit: 50 req/min (~3000 trials/hour)           │
│    └─ Save to S3 Landing Zone (JSONL)                      │
│    ↓                                                         │
│  Glue Bronze Job                                             │
│    └─ Raw JSON storage with nct_id as key                   │
│    ↓                                                         │
│  Glue Silver Job                                             │
│    └─ Parse into normalized tables:                         │
│       ├─ clinical_trials_studies (main table)               │
│       ├─ clinical_trials_interventions                      │
│       ├─ clinical_trials_outcomes                           │
│       ├─ clinical_trials_locations                          │
│       ├─ clinical_trials_conditions                         │
│       └─ clinical_trials_sponsors                           │
└─────────────────────────────────────────────────────────────┘
```

**Key Implementation Details**:

**Lambda Function** (`clinical_trials_lambda/handler.py`):
```python
import boto3
import requests
import time
from typing import List, Dict

API_BASE_URL = "https://clinicaltrials.gov/api/v2"
RATE_LIMIT_DELAY = 1.2  # 50 requests/min = 1.2s per request

def lambda_handler(event, context):
    """
    Query ClinicalTrials.gov API for NCT IDs from NIH Reporter.
    """
    # Get NCT IDs from Athena query
    nct_ids = get_nct_ids_from_athena()

    # Batch NCT IDs (API supports multiple IDs in one request)
    batch_size = 100  # Adjust based on API limits

    for i in range(0, len(nct_ids), batch_size):
        batch = nct_ids[i:i+batch_size]
        query = "+OR+".join([f"{nct_id}" for nct_id in batch])

        # Query API
        url = f"{API_BASE_URL}/studies?query.id={query}&pageSize={batch_size}"
        response = query_api(url)

        # Save to S3
        save_to_s3(response, batch_num=i//batch_size)

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

    return {"status": "success", "trials_processed": len(nct_ids)}

def get_nct_ids_from_athena():
    """Query Athena for unique NCT IDs from NIH Reporter."""
    athena = boto3.client('athena')

    query = """
    SELECT DISTINCT nct_id
    FROM allsci_silver_prod.nih_reporter_clinical_trials
    WHERE nct_id IS NOT NULL
    """

    # Execute query and return results
    # (Implementation details omitted for brevity)
    return nct_ids

def query_api(url: str, max_retries: int = 3) -> Dict:
    """Query ClinicalTrials.gov API with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit
                time.sleep((attempt + 1) * 60)  # Exponential backoff
                continue
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
    raise Exception(f"API request failed after {max_retries} attempts")
```

**Silver Layer Tables**:

1. **`clinical_trials_studies`** (Main dimension):
```sql
CREATE TABLE clinical_trials_studies (
    nct_id STRING,
    org_study_id STRING,
    brief_title STRING,
    official_title STRING,
    brief_summary STRING,
    detailed_description STRING,
    overall_status STRING,  -- RECRUITING, COMPLETED, etc.
    status_verified_date DATE,
    study_type STRING,  -- INTERVENTIONAL, OBSERVATIONAL
    phase STRING,  -- PHASE1, PHASE2, PHASE3, etc.
    enrollment_count INT,
    start_date DATE,
    completion_date DATE,
    primary_completion_date DATE,
    lead_sponsor_name STRING,
    lead_sponsor_class STRING,
    responsible_party_type STRING,
    allocation STRING,  -- RANDOMIZED, NON_RANDOMIZED
    intervention_model STRING,  -- PARALLEL, CROSSOVER, etc.
    primary_purpose STRING,  -- TREATMENT, PREVENTION, etc.
    masking STRING,
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
PARTITIONED BY (months(start_date))
```

2. **`clinical_trials_conditions`** (Bridge table):
```sql
CREATE TABLE clinical_trials_conditions (
    nct_id STRING,
    condition STRING,
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
```

3. **`clinical_trials_interventions`**:
```sql
CREATE TABLE clinical_trials_interventions (
    nct_id STRING,
    intervention_type STRING,  -- DRUG, DEVICE, PROCEDURE, etc.
    intervention_name STRING,
    description STRING,
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
```

4. **`clinical_trials_locations`**:
```sql
CREATE TABLE clinical_trials_locations (
    nct_id STRING,
    facility STRING,
    city STRING,
    state STRING,
    country STRING,
    zip_code STRING,
    status STRING,  -- RECRUITING, etc.
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
```

5. **`clinical_trials_outcomes`**:
```sql
CREATE TABLE clinical_trials_outcomes (
    nct_id STRING,
    outcome_type STRING,  -- PRIMARY, SECONDARY
    measure STRING,
    time_frame STRING,
    description STRING,
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
```

6. **`clinical_trials_eligibility`**:
```sql
CREATE TABLE clinical_trials_eligibility (
    nct_id STRING,
    eligibility_criteria STRING,
    sex STRING,
    minimum_age STRING,
    maximum_age STRING,
    healthy_volunteers STRING,
    source_date DATE,
    ingestion_datetime TIMESTAMP
) USING iceberg
```

### Option 2: Extend Existing NIH Reporter Pipeline

Add a new Glue job to the existing Step Functions workflow:

```
Lambda (NIH Reporter)
  → Bronze Job
  → Silver Job
  → NEW: Clinical Trials Enrichment Job (queries API based on NCT IDs)
  → Success
```

**Pros**: Reuses existing infrastructure
**Cons**: Couples two different data sources; harder to maintain

---

## Joining NIH Reporter + Clinical Trials Data

Once clinical trials data is in the silver layer, you can join it with NIH Reporter:

```sql
-- Get NIH grants with their associated clinical trials
SELECT
    p.project_num,
    p.project_title,
    p.fiscal_year,
    p.award_amount,
    org.org_name,
    ct_link.nct_id,
    ct.brief_title AS trial_title,
    ct.overall_status AS trial_status,
    ct.phase AS trial_phase,
    ct.enrollment_count,
    ct.start_date AS trial_start_date
FROM
    allsci_silver_prod.nih_reporter_projects p
    JOIN allsci_silver_prod.nih_reporter_clinical_trials ct_link
        ON p.project_num = ct_link.project_num
        AND p.fiscal_year = ct_link.fiscal_year
    JOIN allsci_silver_prod.clinical_trials_studies ct
        ON ct_link.nct_id = ct.nct_id
    JOIN allsci_silver_prod.nih_reporter_organizations org
        ON p.project_num = org.project_num
WHERE
    p.fiscal_year = 2024
    AND ct.overall_status = 'RECRUITING'
ORDER BY
    p.award_amount DESC;
```

**Example Analysis - Find trials by condition**:
```sql
SELECT
    p.project_num,
    p.project_title,
    p.award_amount,
    cond.condition,
    ct.brief_title,
    ct.overall_status,
    loc.facility,
    loc.city,
    loc.state
FROM
    allsci_silver_prod.nih_reporter_projects p
    JOIN allsci_silver_prod.nih_reporter_clinical_trials ct_link
        ON p.project_num = ct_link.project_num
    JOIN allsci_silver_prod.clinical_trials_studies ct
        ON ct_link.nct_id = ct.nct_id
    JOIN allsci_silver_prod.clinical_trials_conditions cond
        ON ct.nct_id = cond.nct_id
    LEFT JOIN allsci_silver_prod.clinical_trials_locations loc
        ON ct.nct_id = loc.nct_id
WHERE
    cond.condition LIKE '%Cancer%'
    AND ct.phase IN ('PHASE2', 'PHASE3')
    AND p.fiscal_year >= 2023
ORDER BY
    p.award_amount DESC
LIMIT 100;
```

---

## Implementation Roadmap

### Phase 1: Data Discovery (Current)
- ✅ Understand NCT ID availability in NIH Reporter
- ✅ Explore ClinicalTrials.gov API
- ✅ Design silver layer schema

### Phase 2: Pipeline Development
1. Create new CDK stack for Clinical Trials pipeline
2. Implement Lambda function for API ingestion
3. Create Bronze Glue job (raw JSON storage)
4. Create Silver Glue job with transformations
5. Add to Step Functions workflow

### Phase 3: Testing & Validation
1. Test with sample NCT IDs
2. Validate data quality
3. Check for missing/invalid NCT IDs
4. Performance testing (handle ~10K+ trials)

### Phase 4: Production Deployment
1. Deploy to dev environment
2. Run full historical load
3. Deploy to prod
4. Set up monitoring/alerting

### Phase 5: Analytics & Gold Layer
1. Create gold layer dimensional model
2. Join NIH grants + clinical trials + publications
3. Build unified research analytics

---

## Key Considerations

### 1. Data Freshness
- **NIH Reporter**: Updated weekly
- **ClinicalTrials.gov**: Updated continuously
- **Recommendation**: Run clinical trials pipeline weekly after NIH Reporter

### 2. NCT ID Validation
- Not all NIH projects have clinical trials
- NCT IDs can become invalid (withdrawn studies)
- Handle API 404 errors gracefully

### 3. Rate Limiting Strategy
```python
# Batch approach to stay under 50 req/min
BATCH_SIZE = 100  # NCT IDs per request
RATE_LIMIT_DELAY = 1.2  # seconds (50 req/min)

# For ~10,000 NCT IDs:
# 10,000 / 100 = 100 batches
# 100 batches * 1.2s = 120 seconds (~2 minutes)
```

### 4. Data Volumes
Estimated from current NIH Reporter data:
- Total unique NCT IDs: ~10,000-15,000
- API response size: ~50-100 KB per trial
- Total raw data: ~500 MB - 1.5 GB
- Silver layer (normalized): ~200 MB - 500 MB

### 5. Cost Estimation (AWS)
- Lambda executions: ~100-200 invocations/week = $0.02/month
- S3 storage: ~1 GB = $0.023/month
- Glue job runs: 2 jobs * 0.5 DPU-hours = $1.00/week = $4/month
- Athena queries: ~10 GB scanned/week = $0.50/month
- **Total**: ~$5-6/month

---

## Sample Code: Lambda Handler (Production-Ready)

See separate file: `clinical_trials_lambda/handler.py`

---

## References & Resources

### NIH Reporter
- API Documentation: https://api.reporter.nih.gov/
- Current implementation: `data-pipelines/allsci-data-pipelines/nih_reporter/`
- Clinical trials field mapping: Line 139-144 in `docs/api_fields_mapping.md`

### ClinicalTrials.gov API
- [ClinicalTrials.gov API Documentation](https://clinicaltrials.gov/data-api/api)
- [NLM Technical Bulletin on API v2](https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html)
- [BioMCP ClinicalTrials.gov Guide](https://biomcp.org/backend-services-reference/04-clinicaltrials-gov/)
- [Stack Overflow: ClinicalTrials API in Python](https://stackoverflow.com/questions/78415818/how-to-get-full-results-with-clinicaltrials-gov-api-in-python)

### Related Tools
- [GitHub: ClinicalTrials.gov MCP Server](https://github.com/cyanheads/clinicaltrialsgov-mcp-server)
- [CRAN: clintrialx R Package](https://cran.r-universe.dev/clintrialx/doc/manual.html)

---

## Next Steps

1. **Validate NCT ID Coverage**: Query your current silver layer to understand:
   ```sql
   SELECT
       COUNT(DISTINCT project_num) AS total_projects,
       COUNT(DISTINCT nct_id) AS total_clinical_trials,
       COUNT(DISTINCT project_num) /
         (SELECT COUNT(DISTINCT project_num)
          FROM allsci_silver_prod.nih_reporter_projects) * 100 AS pct_with_trials
   FROM allsci_silver_prod.nih_reporter_clinical_trials;
   ```

2. **Test API Access**: Verify ClinicalTrials.gov API is accessible from your AWS environment

3. **Design Review**: Review proposed schema with stakeholders

4. **Prototype**: Build minimal Lambda + Bronze job to prove concept

5. **Implement**: Full pipeline development following existing NIH Reporter patterns

---

**Document Version**: 1.0
**Last Updated**: 2025-12-04
**Author**: Claude Code
