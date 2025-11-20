# NIH Reporter Pipeline Architecture Refactoring Summary

## Overview

This document summarizes the comprehensive refactoring performed to align the LLM-generated NIH Reporter pipeline with AllSci's 3-layer architecture standards.

## Critical Issues Fixed

### 1. Database Naming & Structure
**Before**: Single database `allsci_{ENV}` with mixed layers  
**After**: Separate databases following AllSci convention
- Bronze: `allsci_{ENV}_nih_reporter_bronze`
- Silver: `allsci_{ENV}_nih_reporter_silver`

### 2. Bronze Layer Table Structure
**Before**: Complex schema with separate columns (project_num, fiscal_year, appl_id, raw_json)  
**After**: Simplified schema following AllSci pattern
```
- project_num (STRING)
- fiscal_year (INT)
- data_object (STRING) - complete raw JSON
- source_date (DATE) - extraction date
- ingestion_datetime (TIMESTAMP)
```

### 3. Silver Layer Architecture
**Before**: Gold-layer dimensional model (dim/fact tables) with AllSci IDs  
**After**: 11 source-specific tables with natural keys

#### Silver Tables Created:
1. `nih_reporter_projects` - Main project data
2. `nih_reporter_organizations` - Organization details
3. `nih_reporter_principal_investigators` - PIs (exploded array)
4. `nih_reporter_program_officers` - Program officers (exploded array)
5. `nih_reporter_publications` - Publications (exploded array)
6. `nih_reporter_clinical_trials` - Clinical trials (exploded array)
7. `nih_reporter_agencies_admin` - Admin IC
8. `nih_reporter_agencies_funding` - Funding ICs (exploded array)
9. `nih_reporter_spending_categories` - Spending categories (exploded array)
10. `nih_reporter_terms` - Research terms (exploded array)
11. `nih_reporter_study_sections` - Study section data

### 4. TransformationCatalog Pattern
**Before**: Manual JSON parsing with complex nested selects  
**After**: Declarative transformer classes registered in TransformationCatalog

Each transformer defines:
- `parse()` - Extract fields from data_object JSON
- `casting_schema` - Data type definitions
- `date_columns` - Date parsing configuration
- `merge_conditions` - Natural keys for upsert
- `extra_columns` - Metadata columns

### 5. Control Flags
**Before**: No processing status tracking  
**After**: S3 control flags in both Bronze and Silver jobs
- Location: `s3://allsci-landingzone-{ENV}/control_flags/{layer}/nih_reporter/flag.json`
- Tracks: batch_to_process, last_updated_at, sources_last_updated_at

### 6. Lambda Handler Data Freshness
**Before**: Generic filenames without source_date tracking  
**After**: Filenames include source_date: `projects_FY{fiscal_year}_{YYYY-MM-DD}_batch*.jsonl`

### 7. Step Functions Arguments
**Before**: No fiscal_years passed to Glue jobs  
**After**: Properly passes `FISCAL_YEARS` argument from input through pipeline

## Files Modified

### Core Pipeline Files
1. `nih_reporter/glue/jobs/nih_reporter_bronze.py` - Complete rewrite for simplified Bronze structure
2. `nih_reporter/glue/jobs/nih_reporter_silver.py` - Complete rewrite using TransformationCatalog
3. `nih_reporter/glue/package/lake_tools/transformations.py` - 11 transformer classes
4. `nih_reporter/glue/package/lake_tools/catalogs.py` - TransformationCatalog registry
5. `nih_reporter/lambda_function/scripts/handler.py` - Added source_date tracking
6. `nih_reporter/step_functions/step_functions_app_construct.py` - Fixed argument passing

### Documentation & Schema
7. `nih_reporter/.sql/athena.sql` - Created with proper Bronze/Silver table definitions
8. `nih_reporter/README.md` - Updated architecture, schema, and query examples

## Key Architectural Principles Applied

### 1. Silver = Source Tables
Silver layer tables represent data from ONE source (NIH Reporter), preserving source-specific structure with natural keys (project_num + fiscal_year).

### 2. No AllSci IDs in Silver
AllSci standardized IDs (ASC-GR-*) will be generated in the **Gold layer** (future work), not Silver.

### 3. Data Flow
```
Landing Zone (JSONL with source_date)
    ↓
Bronze (minimal metadata + data_object)
    ↓
Silver (11 normalized source tables)
    ↓
Gold (future: dimensional model with AllSci IDs)
```

### 4. Natural Keys Throughout Silver
All Silver tables use natural keys:
- Primary: project_num + fiscal_year
- Organizations: org_key (md5 hash)
- PIs: profile_id
- Publications: pmid
- Clinical Trials: nct_id

### 5. Partitioning Strategy
Most tables partitioned by `fiscal_year` as NIH Reporter processes by fiscal year (~200K-500K records/year), not daily.

## Testing Checklist

Before deploying to production:

- [ ] Create Bronze database: `allsci_{ENV}_nih_reporter_bronze`
- [ ] Create Silver database: `allsci_{ENV}_nih_reporter_silver`
- [ ] Run SQL schema creation from `.sql/athena.sql`
- [ ] Test Lambda handler with sample fiscal year
- [ ] Verify Bronze job reads JSONL and creates data_object correctly
- [ ] Verify Silver job creates all 11 tables
- [ ] Check control flag updates in S3
- [ ] Validate query examples in README work correctly
- [ ] Test complete pipeline via Step Functions

## Future Work: Gold Layer

The dimensional model (dim/fact tables) should be created in a separate **Gold layer pipeline** that:
- Combines NIH Reporter with other grant sources (NSF, private foundations, etc.)
- Generates AllSci IDs (ASC-GR-*)
- Creates unified dimensional model:
  - `dim_grant` (with AllSci IDs)
  - `fact_grant_funding`
  - Other cross-source dimensions

## Migration Notes

If upgrading from LLM-generated version:

1. **Backup existing data** from old tables
2. **Drop old tables** (dim_nih_grants, fact_nih_funding, etc.)
3. **Create new databases** (bronze, silver)
4. **Deploy updated CDK stack**
5. **Run pipeline** to populate new tables
6. **Update downstream queries** to use new table names

## References

- AllSci Architecture Pattern: `nih_clinical_trials_gov` pipeline
- TransformationCatalog: `lake_tools/catalogs.py` and `lake_tools/transformations.py`
- Control Flags: `utils/functions.py` (read_json_from_s3, write_json_to_s3)

