/*
###################
## BRONZE TABLES ##
###################
*/

CREATE TABLE allsci_<env>_nih_reporter_bronze.projects_metadata (
  project_num STRING COMMENT 'Project/grant number (natural key)',
  fiscal_year INT COMMENT 'Fiscal year for partitioning',
  data_object STRING COMMENT 'Complete raw JSON data from API',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested into bronze'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-bronze-<env>/nih_reporter/projects_metadata'
TBLPROPERTIES (
  'table_type'='iceberg',
  'write_compression'='zstd',
  'format'='parquet'
);

/*
###################
## SILVER TABLES ##
###################
*/

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_projects (
  project_num STRING COMMENT 'Project/grant number (natural key)',
  fiscal_year INT COMMENT 'Fiscal year',
  appl_id BIGINT COMMENT 'Application ID',
  subproject_id STRING COMMENT 'Subproject ID for multi-project awards',
  project_serial_num STRING COMMENT 'Serial number portion of project number',
  core_project_num STRING COMMENT 'Core project number',
  activity_code STRING COMMENT 'NIH activity code',
  project_title STRING COMMENT 'Project title',
  project_start_date DATE COMMENT 'Project start date',
  project_end_date DATE COMMENT 'Project end date',
  budget_start_date DATE COMMENT 'Budget period start date',
  budget_end_date DATE COMMENT 'Budget period end date',
  award_notice_date DATE COMMENT 'Award notice date',
  award_type STRING COMMENT 'Type of award',
  award_amount BIGINT COMMENT 'Total award amount',
  direct_cost_amt BIGINT COMMENT 'Direct costs',
  indirect_cost_amt BIGINT COMMENT 'Indirect costs',
  total_cost BIGINT COMMENT 'Total cost',
  total_cost_sub_project BIGINT COMMENT 'Subproject total cost',
  abstract_text STRING COMMENT 'Project abstract',
  phr_text STRING COMMENT 'Public health relevance statement',
  project_detail_url STRING COMMENT 'URL to project details on RePORTER',
  contact_pi_name STRING COMMENT 'Contact PI name',
  publication_count INT COMMENT 'Number of publications',
  arra_funded STRING COMMENT 'ARRA funded indicator',
  funding_mechanism STRING COMMENT 'Funding mechanism description',
  cfda_code STRING COMMENT 'CFDA code',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_projects'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_organizations (
  org_key STRING COMMENT 'Hash-based surrogate key (md5 of name+city+state)',
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  org_name STRING COMMENT 'Organization name',
  org_city STRING COMMENT 'Organization city',
  org_state STRING COMMENT 'Organization state code',
  org_state_name STRING COMMENT 'Organization state name',
  org_country STRING COMMENT 'Organization country',
  org_zipcode STRING COMMENT 'Organization ZIP code',
  org_fips STRING COMMENT 'FIPS county code',
  dept_type STRING COMMENT 'Department type',
  org_duns STRING COMMENT 'DUNS number',
  org_uei STRING COMMENT 'Unique Entity Identifier',
  org_ipf_code STRING COMMENT 'IPF code',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_organizations'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_principal_investigators (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  profile_id BIGINT COMMENT 'PI profile ID',
  first_name STRING COMMENT 'First name',
  middle_name STRING COMMENT 'Middle name',
  last_name STRING COMMENT 'Last name',
  full_name STRING COMMENT 'Full name',
  is_contact_pi BOOLEAN COMMENT 'Is contact PI flag',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_principal_investigators'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_program_officers (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  first_name STRING COMMENT 'First name',
  middle_name STRING COMMENT 'Middle name',
  last_name STRING COMMENT 'Last name',
  full_name STRING COMMENT 'Full name',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_program_officers'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_publications (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  pmid BIGINT COMMENT 'PubMed ID',
  pmc_id STRING COMMENT 'PubMed Central ID',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_publications'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_clinical_trials (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  nct_id STRING COMMENT 'ClinicalTrials.gov NCT ID',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_clinical_trials'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_agencies_admin (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  ic_code STRING COMMENT 'Institute/Center code',
  ic_abbreviation STRING COMMENT 'Institute/Center abbreviation',
  ic_name STRING COMMENT 'Institute/Center name',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_agencies_admin'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_agencies_funding (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  ic_code STRING COMMENT 'Institute/Center code',
  ic_abbreviation STRING COMMENT 'Institute/Center abbreviation',
  ic_name STRING COMMENT 'Institute/Center name',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_agencies_funding'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_spending_categories (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  category_name STRING COMMENT 'Spending category name',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_spending_categories'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_terms (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  term_text STRING COMMENT 'Research term text',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_terms'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

CREATE TABLE allsci_<env>_nih_reporter_silver.nih_reporter_study_sections (
  project_num STRING COMMENT 'Project/grant number',
  fiscal_year INT COMMENT 'Fiscal year',
  srg_code STRING COMMENT 'Scientific Review Group code',
  srg_flex STRING COMMENT 'SRG flex',
  sra_designator_code STRING COMMENT 'SRA designator code',
  sra_flex_code STRING COMMENT 'SRA flex code',
  group_code STRING COMMENT 'Group code',
  study_section_name STRING COMMENT 'Study section name',
  source_date DATE COMMENT 'Date when data was extracted from API',
  ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested'
)
PARTITIONED BY (fiscal_year)
LOCATION 's3://allsci-silver-<env>/nih_reporter/nih_reporter_study_sections'
TBLPROPERTIES (
  'table_type'='iceberg',
  'format'='parquet',
  'write_compression'='zstd'
);

