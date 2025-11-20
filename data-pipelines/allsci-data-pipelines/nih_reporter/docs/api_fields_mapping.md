# NIH RePORTER API v2 - Complete Field Mapping

## API Overview

**Base URL**: https://api.reporter.nih.gov
**Primary Endpoint**: POST /v2/projects/search
**Rate Limit**: Maximum 1 request per second
**Pagination**: max 500 records per request, max offset 14,999

## Response Structure

```json
{
  "meta": {
    "total": <integer>  // Total number of matching records
  },
  "results": [
    // Array of project objects
  ]
}
```

## Complete Field Inventory

Based on API exploration and documentation review, the following fields are available in the NIH RePORTER API v2 project responses:

### 1. PROJECT IDENTIFIERS & CORE INFO

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `appl_id` | Integer | Application ID | dim_nih_grants | appl_id |
| `subproject_id` | Integer/String | Subproject ID (for multi-project awards) | dim_nih_grants | subproject_id |
| `project_num` | String | Full project/grant number | dim_nih_grants | project_num |
| `project_serial_num` | String | Serial number portion of project number | dim_nih_grants | project_serial_num |
| `project_num_split` | Object | Parsed components of project number | dim_nih_grants | project_num_split_json |
| `core_project_num` | String | Core project number | dim_nih_grants | core_project_num |
| `fiscal_year` | Integer | Fiscal year of award | fact_nih_funding | fiscal_year |
| `project_title` | String | Project title | dim_nih_grants | project_title |
| `project_start_date` | String (Date) | Project start date | dim_nih_grants | project_start_date |
| `project_end_date` | String (Date) | Project end date | dim_nih_grants | project_end_date |
| `budget_start` | String (Date) | Budget period start date | fact_nih_funding | budget_start_date |
| `budget_end` | String (Date) | Budget period end date | fact_nih_funding | budget_end_date |
| `award_type` | String | Type of award | fact_nih_funding | award_type |
| `activity_code` | String | NIH activity code | dim_nih_grants | activity_code |
| `award_notice_date` | String (Date) | Date award was issued | fact_nih_funding | award_notice_date |

### 2. TEXTUAL CONTENT

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `abstract_text` | String | Project abstract | dim_nih_grants | abstract_text |
| `project_detail_url` | String | URL to project details on RePORTER | dim_nih_grants | project_detail_url |
| `phr_text` | String | Public health relevance statement | dim_nih_grants | phr_text |
| `all_text` | String | Combined searchable text | dim_nih_grants | all_text |
| `terms` | String/Array | Research terms/keywords | bridge_nih_terms | term_text |

### 3. ORGANIZATION INFORMATION

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `organization` | Object | Organization details (nested) | dim_nih_organizations | - |
| `organization.org_name` | String | Organization name | dim_nih_organizations | org_name |
| `organization.org_city` | String | City | dim_nih_organizations | org_city |
| `organization.org_state` | String | State code | dim_nih_organizations | org_state |
| `organization.org_state_name` | String | State name | dim_nih_organizations | org_state_name |
| `organization.org_country` | String | Country | dim_nih_organizations | org_country |
| `organization.org_zipcode` | String | ZIP code | dim_nih_organizations | org_zipcode |
| `organization.org_fips` | String | FIPS county code | dim_nih_organizations | org_fips |
| `organization.dept_type` | String | Department type | dim_nih_organizations | dept_type |
| `organization.org_duns` | String | DUNS number | dim_nih_organizations | org_duns |
| `organization.org_uei` | String | Unique Entity Identifier | dim_nih_organizations | org_uei |
| `organization.org_ipf_code` | String | IPF code | dim_nih_organizations | org_ipf_code |

### 4. PRINCIPAL INVESTIGATORS & PERSONNEL

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `principal_investigators` | Array | List of PIs (nested) | dim_nih_personnel | - |
| `principal_investigators[].profile_id` | Integer | PI profile ID | dim_nih_personnel | profile_id |
| `principal_investigators[].first_name` | String | First name | dim_nih_personnel | first_name |
| `principal_investigators[].middle_name` | String | Middle name | dim_nih_personnel | middle_name |
| `principal_investigators[].last_name` | String | Last name | dim_nih_personnel | last_name |
| `principal_investigators[].is_contact_pi` | Boolean | Is contact PI flag | dim_nih_personnel | is_contact_pi |
| `principal_investigators[].full_name` | String | Full name | dim_nih_personnel | full_name |
| `contact_pi_name` | String | Contact PI name (denormalized) | dim_nih_grants | contact_pi_name |
| `program_officers` | Array | List of program officers | dim_nih_personnel | - |
| `program_officers[].first_name` | String | First name | dim_nih_personnel | first_name |
| `program_officers[].middle_name` | String | Middle name | dim_nih_personnel | middle_name |
| `program_officers[].last_name` | String | Last name | dim_nih_personnel | last_name |
| `program_officers[].full_name` | String | Full name | dim_nih_personnel | full_name |

### 5. FUNDING & BUDGET

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `award_amount` | Integer | Total award amount | fact_nih_funding | award_amount |
| `direct_cost_amt` | Integer | Direct costs | fact_nih_funding | direct_cost_amt |
| `indirect_cost_amt` | Integer | Indirect costs | fact_nih_funding | indirect_cost_amt |
| `arra_funded` | String | ARRA funded indicator | fact_nih_funding | arra_funded |
| `funding_mechanism` | String | Funding mechanism description | fact_nih_funding | funding_mechanism |
| `cfda_code` | String | CFDA code | fact_nih_funding | cfda_code |
| `total_cost` | Integer | Total cost | fact_nih_funding | total_cost |
| `total_cost_sub_project` | Integer | Subproject total cost | fact_nih_funding | total_cost_sub_project |

### 6. STUDY SECTION & REVIEW

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `full_study_section` | Object | Study section details | dim_nih_study_sections | - |
| `full_study_section.srg_code` | String | Scientific Review Group code | dim_nih_study_sections | srg_code |
| `full_study_section.srg_flex` | String | SRG flex | dim_nih_study_sections | srg_flex |
| `full_study_section.sra_designator_code` | String | SRA designator code | dim_nih_study_sections | sra_designator_code |
| `full_study_section.sra_flex_code` | String | SRA flex code | dim_nih_study_sections | sra_flex_code |
| `full_study_section.group_code` | String | Group code | dim_nih_study_sections | group_code |
| `full_study_section.name` | String | Study section name | dim_nih_study_sections | study_section_name |

### 7. NIH INSTITUTE/CENTER (IC) INFORMATION

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `agency_ic_admin` | Object | Administering IC | dim_nih_agencies | - |
| `agency_ic_admin.code` | String | IC code | dim_nih_agencies | ic_code |
| `agency_ic_admin.abbreviation` | String | IC abbreviation | dim_nih_agencies | ic_abbreviation |
| `agency_ic_admin.name` | String | IC name | dim_nih_agencies | ic_name |
| `agency_ic_fundings` | Array | Funding ICs | dim_nih_agencies | - |
| `agency_ic_fundings[].code` | String | IC code | dim_nih_agencies | ic_code |
| `agency_ic_fundings[].abbreviation` | String | IC abbreviation | dim_nih_agencies | ic_abbreviation |
| `agency_ic_fundings[].name` | String | IC name | dim_nih_agencies | ic_name |

### 8. PUBLICATIONS

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `publications` | Array | List of publications | bridge_nih_publications | - |
| `publications[].pmid` | Integer | PubMed ID | bridge_nih_publications | pmid |
| `publications[].pmc_id` | String | PubMed Central ID | bridge_nih_publications | pmc_id |
| `publication_count` | Integer | Total publication count | dim_nih_grants | publication_count |

### 9. CLINICAL TRIALS

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `clinical_trials` | Array | Clinical trial IDs | bridge_nih_clinical_trials | - |
| `clinical_trials[].nct_id` | String | ClinicalTrials.gov ID | bridge_nih_clinical_trials | nct_id |

### 10. SPENDING CATEGORIES

| API Field Name | Data Type | Description | Silver Table | Silver Column |
|----------------|-----------|-------------|--------------|---------------|
| `spending_categories` | Array | NIH spending categories | bridge_nih_spending_categories | - |
| `spending_categories[].name` | String | Category name | bridge_nih_spending_categories | category_name |

### 11. METADATA FIELDS (Added by Pipeline)

| Field Name | Data Type | Description | Silver Table | Silver Column |
|------------|-----------|-------------|--------------|---------------|
| `source_file` | String | S3 source file path | All tables | source_file |
| `ingestion_timestamp` | Timestamp | When data was ingested | All tables | ingestion_timestamp |
| `processed_timestamp` | Timestamp | When data was processed | All tables | processed_timestamp |
| `pipeline_version` | String | Pipeline version | All tables | pipeline_version |

## Silver Layer Schema Design

### Dimension Tables

#### `dim_nih_grants`
Primary dimension table for project core attributes.
- **Primary Key**: `allsci_id` (AllSci Grant ID: ASC-GR-{sequence}-1.0-{timestamp})
- **Natural Keys**: `project_num`, `fiscal_year`
- **Sequence Tracking**: `allsci_id_numeric_part`
- **Attributes**: All project-level fields from section 1, 2, plus denormalized contact_pi_name

#### `dim_nih_organizations`
Organization/institution dimension.
- **Primary Key**: Composite of org_name, org_city, org_state
- **Attributes**: All organization fields from section 3

#### `dim_nih_personnel`
Personnel dimension (PIs and Program Officers).
- **Primary Key**: `profile_id`, `project_num`, `fiscal_year`, `role_type`
- **Attributes**: Name fields, role indicator

#### `dim_nih_study_sections`
Study section dimension.
- **Primary Key**: `srg_code`
- **Attributes**: All study section fields from section 6

#### `dim_nih_agencies`
NIH Institute/Center dimension.
- **Primary Key**: `ic_code`
- **Attributes**: IC abbreviation, name

### Fact Tables

#### `fact_nih_funding`
Main fact table for award/funding events.
- **Primary Key**: `funding_key`
- **Foreign Keys**: 
  - `grant_allsci_id` -> dim_nih_grants.allsci_id
  - `org_key` -> dim_nih_organizations.org_key
  - `admin_ic_key` -> dim_nih_agencies.agency_key
- **Natural Keys**: `project_num`, `fiscal_year`
- **Measures**: award_amount, direct_cost_amt, indirect_cost_amt, total_cost
- **Attributes**: Dates, award type, funding mechanism

### Bridge Tables

#### `bridge_nih_publications`
Many-to-many relationship between projects and publications.
- **Composite Key**: `project_num`, `fiscal_year`, `pmid`

#### `bridge_nih_clinical_trials`
Many-to-many relationship between projects and clinical trials.
- **Composite Key**: `project_num`, `fiscal_year`, `nct_id`

#### `bridge_nih_spending_categories`
Many-to-many relationship between projects and spending categories.
- **Composite Key**: `project_num`, `fiscal_year`, `category_name`

#### `bridge_nih_terms`
Many-to-many relationship between projects and research terms.
- **Composite Key**: `project_num`, `fiscal_year`, `term_text`

## Data Quality Considerations

1. **Nullability**: Most fields can be null/missing
2. **Duplicates**: Projects can appear in multiple fiscal years
3. **Updates**: Project data can be updated; use upsert logic
4. **Array Fields**: Handle variable-length arrays (PIs, publications, etc.)

## Query Examples

### Get all projects for an organization
```sql
SELECT g.*, f.*
FROM dim_nih_grants g
JOIN fact_nih_funding f ON g.allsci_id = f.grant_allsci_id
JOIN dim_nih_organizations o ON f.org_key = o.org_key
WHERE o.org_name = 'UNIVERSITY OF CALIFORNIA, SAN FRANCISCO'
AND f.fiscal_year = 2024;
```

### Get PI publication counts
```sql
SELECT
    pers.full_name,
    COUNT(DISTINCT pub.pmid) as publication_count,
    SUM(f.award_amount) as total_funding
FROM dim_nih_personnel pers
JOIN fact_nih_funding f ON pers.project_num = f.project_num
LEFT JOIN bridge_nih_publications pub ON f.project_num = pub.project_num
WHERE pers.role_type = 'PI'
GROUP BY pers.full_name
ORDER BY total_funding DESC;
```

## Additional Resources

- [Official API Documentation](https://api.reporter.nih.gov/)
- [Data Elements PDF](https://api.reporter.nih.gov/documents/Data%20Elements%20for%20RePORTER%20Project%20API_V2.pdf)
- [Sample API Requests](https://api.reporter.nih.gov/documents/Sample%20RePORTER%20API%20Request%20Matching%20ExPORTER%20Project%20Files.pdf)
