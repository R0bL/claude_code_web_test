"""
NIH RePORTER Silver Layer Glue Job

This Glue job transforms bronze layer data into normalized silver layer tables,
creating a star schema with dimension and fact tables that capture ALL fields
from the NIH RePORTER API.

Tables created:
- dim_nih_projects: Core project dimension
- dim_nih_organizations: Organization dimension
- dim_nih_personnel: Personnel dimension (PIs and Program Officers)
- dim_nih_study_sections: Study section dimension
- dim_nih_agencies: NIH Institute/Center dimension
- fact_nih_funding: Funding fact table
- bridge_nih_publications: Project-publication bridge
- bridge_nih_clinical_trials: Project-clinical trial bridge
- bridge_nih_spending_categories: Project-spending category bridge
- bridge_nih_terms: Project-research terms bridge

Author: AllSci Data Pipeline
"""

import sys
from datetime import datetime
from typing import List

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, explode, explode_outer, get_json_object,
    from_json, lit, md5, concat, array, when, coalesce, trim, size, to_date
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType,
    DoubleType, BooleanType, ArrayType, TimestampType, DateType
)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'bronze_bucket',
    'silver_bucket',
    'environment',
    'glue_database',
    'fiscal_years'
])

# Initialize contexts
sc = SparkContext()
glue_context = GlueContext(sc)
spark: SparkSession = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# Configure Iceberg
spark.conf.set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", f"s3://{args['silver_bucket']}/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")

# Job configuration
BRONZE_BUCKET = args['bronze_bucket']
SILVER_BUCKET = args['silver_bucket']
ENVIRONMENT = args['environment']
GLUE_DATABASE = args['glue_database']
FISCAL_YEARS = [int(fy.strip()) for fy in args['fiscal_years'].split(',')]
PIPELINE_VERSION = "1.0.0"

# Table names
BRONZE_TABLE = f"glue_catalog.{GLUE_DATABASE}.nih_reporter_projects_bronze"
SILVER_TABLES = {
    'dim_projects': f"glue_catalog.{GLUE_DATABASE}.dim_nih_projects",
    'dim_organizations': f"glue_catalog.{GLUE_DATABASE}.dim_nih_organizations",
    'dim_personnel': f"glue_catalog.{GLUE_DATABASE}.dim_nih_personnel",
    'dim_study_sections': f"glue_catalog.{GLUE_DATABASE}.dim_nih_study_sections",
    'dim_agencies': f"glue_catalog.{GLUE_DATABASE}.dim_nih_agencies",
    'fact_funding': f"glue_catalog.{GLUE_DATABASE}.fact_nih_funding",
    'bridge_publications': f"glue_catalog.{GLUE_DATABASE}.bridge_nih_publications",
    'bridge_clinical_trials': f"glue_catalog.{GLUE_DATABASE}.bridge_nih_clinical_trials",
    'bridge_spending_categories': f"glue_catalog.{GLUE_DATABASE}.bridge_nih_spending_categories",
    'bridge_terms': f"glue_catalog.{GLUE_DATABASE}.bridge_nih_terms"
}


def main():
    """Main execution function."""
    try:
        print(f"Starting Silver layer job for fiscal years: {FISCAL_YEARS}")
        print(f"Environment: {ENVIRONMENT}")

        # Create all silver tables if they don't exist
        create_all_silver_tables()

        # Read bronze data
        bronze_df = read_bronze_data()

        if bronze_df.count() == 0:
            print("No bronze data found to process")
            job.commit()
            return

        # Parse raw JSON into structured DataFrame
        parsed_df = parse_bronze_json(bronze_df)

        # Transform into dimension and fact tables
        print("Creating dimension tables...")
        create_dim_projects(parsed_df)
        create_dim_organizations(parsed_df)
        create_dim_personnel(parsed_df)
        create_dim_study_sections(parsed_df)
        create_dim_agencies(parsed_df)

        print("Creating fact tables...")
        create_fact_funding(parsed_df)

        print("Creating bridge tables...")
        create_bridge_publications(parsed_df)
        create_bridge_clinical_trials(parsed_df)
        create_bridge_spending_categories(parsed_df)
        create_bridge_terms(parsed_df)

        print("Silver layer job completed successfully")
        job.commit()

    except Exception as e:
        print(f"Error in silver layer job: {str(e)}")
        raise


def create_all_silver_tables():
    """Create all silver layer Iceberg tables if they don't exist."""

    # dim_nih_projects
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['dim_projects']} (
        project_key STRING COMMENT 'Surrogate key',
        project_num STRING COMMENT 'Project/grant number',
        fiscal_year INT COMMENT 'Fiscal year',
        appl_id BIGINT COMMENT 'Application ID',
        subproject_id STRING COMMENT 'Subproject ID',
        core_project_num STRING COMMENT 'Core project number',
        project_serial_num STRING COMMENT 'Project serial number',
        activity_code STRING COMMENT 'Activity code',
        project_title STRING COMMENT 'Project title',
        project_start_date DATE COMMENT 'Project start date',
        project_end_date DATE COMMENT 'Project end date',
        abstract_text STRING COMMENT 'Project abstract',
        phr_text STRING COMMENT 'Public health relevance',
        all_text STRING COMMENT 'All searchable text',
        project_detail_url STRING COMMENT 'RePORTER URL',
        contact_pi_name STRING COMMENT 'Contact PI name',
        publication_count INT COMMENT 'Number of publications',
        project_num_split_json STRING COMMENT 'Project number components as JSON',
        source_file STRING COMMENT 'Source bronze file',
        processing_timestamp TIMESTAMP COMMENT 'Processing timestamp',
        pipeline_version STRING COMMENT 'Pipeline version'
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/dim_projects/'
    """)

    # dim_nih_organizations
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['dim_organizations']} (
        org_key STRING COMMENT 'Surrogate key',
        org_name STRING COMMENT 'Organization name',
        org_city STRING COMMENT 'City',
        org_state STRING COMMENT 'State code',
        org_state_name STRING COMMENT 'State name',
        org_country STRING COMMENT 'Country',
        org_zipcode STRING COMMENT 'ZIP code',
        org_fips STRING COMMENT 'FIPS county code',
        dept_type STRING COMMENT 'Department type',
        org_duns STRING COMMENT 'DUNS number',
        org_uei STRING COMMENT 'Unique Entity Identifier',
        org_ipf_code STRING COMMENT 'IPF code',
        processing_timestamp TIMESTAMP COMMENT 'Processing timestamp',
        pipeline_version STRING COMMENT 'Pipeline version'
    )
    USING iceberg
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/dim_organizations/'
    """)

    # dim_nih_personnel
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['dim_personnel']} (
        personnel_key STRING COMMENT 'Surrogate key',
        project_num STRING COMMENT 'Project number',
        fiscal_year INT COMMENT 'Fiscal year',
        role_type STRING COMMENT 'PI or PO',
        profile_id BIGINT COMMENT 'Profile ID',
        first_name STRING COMMENT 'First name',
        middle_name STRING COMMENT 'Middle name',
        last_name STRING COMMENT 'Last name',
        full_name STRING COMMENT 'Full name',
        is_contact_pi BOOLEAN COMMENT 'Is contact PI',
        processing_timestamp TIMESTAMP COMMENT 'Processing timestamp',
        pipeline_version STRING COMMENT 'Pipeline version'
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/dim_personnel/'
    """)

    # dim_nih_study_sections
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['dim_study_sections']} (
        study_section_key STRING COMMENT 'Surrogate key',
        srg_code STRING COMMENT 'Scientific Review Group code',
        srg_flex STRING COMMENT 'SRG flex',
        sra_designator_code STRING COMMENT 'SRA designator code',
        sra_flex_code STRING COMMENT 'SRA flex code',
        group_code STRING COMMENT 'Group code',
        study_section_name STRING COMMENT 'Study section name',
        processing_timestamp TIMESTAMP COMMENT 'Processing timestamp',
        pipeline_version STRING COMMENT 'Pipeline version'
    )
    USING iceberg
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/dim_study_sections/'
    """)

    # dim_nih_agencies
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['dim_agencies']} (
        agency_key STRING COMMENT 'Surrogate key',
        ic_code STRING COMMENT 'IC code',
        ic_abbreviation STRING COMMENT 'IC abbreviation',
        ic_name STRING COMMENT 'IC name',
        agency_type STRING COMMENT 'admin or funding',
        processing_timestamp TIMESTAMP COMMENT 'Processing timestamp',
        pipeline_version STRING COMMENT 'Pipeline version'
    )
    USING iceberg
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/dim_agencies/'
    """)

    # fact_nih_funding
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['fact_funding']} (
        funding_key STRING COMMENT 'Surrogate key',
        project_num STRING COMMENT 'Project number',
        fiscal_year INT COMMENT 'Fiscal year',
        award_amount BIGINT COMMENT 'Award amount',
        direct_cost_amt BIGINT COMMENT 'Direct costs',
        indirect_cost_amt BIGINT COMMENT 'Indirect costs',
        total_cost BIGINT COMMENT 'Total cost',
        total_cost_sub_project BIGINT COMMENT 'Subproject total cost',
        budget_start_date DATE COMMENT 'Budget start',
        budget_end_date DATE COMMENT 'Budget end',
        award_notice_date DATE COMMENT 'Award notice date',
        award_type STRING COMMENT 'Award type',
        arra_funded STRING COMMENT 'ARRA funded indicator',
        funding_mechanism STRING COMMENT 'Funding mechanism',
        cfda_code STRING COMMENT 'CFDA code',
        org_key STRING COMMENT 'FK to dim_organizations',
        admin_ic_key STRING COMMENT 'FK to dim_agencies',
        processing_timestamp TIMESTAMP COMMENT 'Processing timestamp',
        pipeline_version STRING COMMENT 'Pipeline version'
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/fact_funding/'
    """)

    # Bridge tables
    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['bridge_publications']} (
        project_num STRING,
        fiscal_year INT,
        pmid BIGINT,
        pmc_id STRING,
        processing_timestamp TIMESTAMP,
        pipeline_version STRING
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/bridge_publications/'
    """)

    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['bridge_clinical_trials']} (
        project_num STRING,
        fiscal_year INT,
        nct_id STRING,
        processing_timestamp TIMESTAMP,
        pipeline_version STRING
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/bridge_clinical_trials/'
    """)

    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['bridge_spending_categories']} (
        project_num STRING,
        fiscal_year INT,
        category_name STRING,
        processing_timestamp TIMESTAMP,
        pipeline_version STRING
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/bridge_spending_categories/'
    """)

    spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['bridge_terms']} (
        project_num STRING,
        fiscal_year INT,
        term_text STRING,
        processing_timestamp TIMESTAMP,
        pipeline_version STRING
    )
    USING iceberg
    PARTITIONED BY (fiscal_year)
    LOCATION 's3://{SILVER_BUCKET}/nih_reporter/bridge_terms/'
    """)

    print("All silver tables created/verified")


def read_bronze_data() -> DataFrame:
    """Read data from bronze layer for specified fiscal years."""
    fiscal_year_filter = " OR ".join([f"fiscal_year = {fy}" for fy in FISCAL_YEARS])

    df = spark.sql(f"""
        SELECT *
        FROM {BRONZE_TABLE}
        WHERE {fiscal_year_filter}
    """)

    print(f"Read {df.count()} records from bronze layer")
    return df


def parse_bronze_json(bronze_df: DataFrame) -> DataFrame:
    """
    Parse raw_json column into structured DataFrame.

    This extracts all fields from the JSON structure.
    """
    # Define comprehensive schema based on API exploration
    # This schema captures ALL known fields from the NIH RePORTER API

    parsed_df = bronze_df.select(
        col('fiscal_year'),
        col('project_num'),
        col('source_file'),
        col('processing_timestamp').alias('bronze_processing_timestamp'),
        from_json(col('raw_json'), get_json_schema()).alias('data')
    ).select(
        col('fiscal_year'),
        col('project_num'),
        col('source_file'),
        col('bronze_processing_timestamp'),
        col('data.*')
    )

    return parsed_df


def get_json_schema() -> str:
    """
    Return JSON schema string for parsing raw_json.
    This is a comprehensive schema covering all API fields.
    """
    # Return a schema that handles the complete NIH RePORTER response
    # Using schema inference for flexibility
    return """
    struct<
        appl_id: bigint,
        subproject_id: string,
        project_num: string,
        project_serial_num: string,
        project_num_split: struct<
            appl_type_code: string,
            activity_code: string,
            ic_code: string,
            serial_num: string,
            support_year: string,
            full_support_year: string,
            suffix_code: string
        >,
        core_project_num: string,
        fiscal_year: int,
        project_title: string,
        project_start_date: string,
        project_end_date: string,
        budget_start: string,
        budget_end: string,
        award_type: string,
        activity_code: string,
        award_notice_date: string,
        abstract_text: string,
        project_detail_url: string,
        phr_text: string,
        all_text: string,
        terms: array<string>,
        contact_pi_name: string,
        organization: struct<
            org_name: string,
            org_city: string,
            org_state: string,
            org_state_name: string,
            org_country: string,
            org_zipcode: string,
            org_fips: string,
            dept_type: string,
            org_duns: string,
            org_uei: string,
            org_ipf_code: string
        >,
        principal_investigators: array<struct<
            profile_id: bigint,
            first_name: string,
            middle_name: string,
            last_name: string,
            full_name: string,
            is_contact_pi: boolean
        >>,
        program_officers: array<struct<
            first_name: string,
            middle_name: string,
            last_name: string,
            full_name: string
        >>,
        award_amount: bigint,
        direct_cost_amt: bigint,
        indirect_cost_amt: bigint,
        total_cost: bigint,
        total_cost_sub_project: bigint,
        arra_funded: string,
        funding_mechanism: string,
        cfda_code: string,
        full_study_section: struct<
            srg_code: string,
            srg_flex: string,
            sra_designator_code: string,
            sra_flex_code: string,
            group_code: string,
            name: string
        >,
        agency_ic_admin: struct<
            code: string,
            abbreviation: string,
            name: string
        >,
        agency_ic_fundings: array<struct<
            code: string,
            abbreviation: string,
            name: string
        >>,
        publications: array<struct<
            pmid: bigint,
            pmc_id: string
        >>,
        publication_count: int,
        clinical_trials: array<struct<
            nct_id: string
        >>,
        spending_categories: array<struct<
            name: string
        >>
    >
    """


def create_dim_projects(df: DataFrame):
    """Create/update dim_nih_projects dimension table."""
    projects_df = df.select(
        md5(concat(col('project_num'), lit('_'), col('fiscal_year'))).alias('project_key'),
        col('project_num'),
        col('fiscal_year'),
        col('appl_id'),
        col('subproject_id'),
        col('core_project_num'),
        col('project_serial_num'),
        col('activity_code'),
        col('project_title'),
        to_date(col('project_start_date')).alias('project_start_date'),
        to_date(col('project_end_date')).alias('project_end_date'),
        col('abstract_text'),
        col('phr_text'),
        col('all_text'),
        col('project_detail_url'),
        col('contact_pi_name'),
        col('publication_count'),
        col('project_num_split').cast(StringType()).alias('project_num_split_json'),
        col('source_file'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    ).dropDuplicates(['project_num', 'fiscal_year'])

    write_to_table(projects_df, 'dim_projects', ['project_num', 'fiscal_year'])


def create_dim_organizations(df: DataFrame):
    """Create/update dim_nih_organizations dimension table."""
    orgs_df = df.select(
        col('organization.*')
    ).dropDuplicates().filter(col('org_name').isNotNull())

    orgs_df = orgs_df.select(
        md5(concat(
            coalesce(col('org_name'), lit('')),
            lit('_'),
            coalesce(col('org_city'), lit('')),
            lit('_'),
            coalesce(col('org_state'), lit(''))
        )).alias('org_key'),
        col('org_name'),
        col('org_city'),
        col('org_state'),
        col('org_state_name'),
        col('org_country'),
        col('org_zipcode'),
        col('org_fips'),
        col('dept_type'),
        col('org_duns'),
        col('org_uei'),
        col('org_ipf_code'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    )

    write_to_table(orgs_df, 'dim_organizations', ['org_key'])


def create_dim_personnel(df: DataFrame):
    """Create/update dim_nih_personnel dimension table."""
    # Extract PIs
    pis_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        explode_outer(col('principal_investigators')).alias('pi')
    ).select(
        col('project_num'),
        col('fiscal_year'),
        lit('PI').alias('role_type'),
        col('pi.profile_id').alias('profile_id'),
        col('pi.first_name').alias('first_name'),
        col('pi.middle_name').alias('middle_name'),
        col('pi.last_name').alias('last_name'),
        col('pi.full_name').alias('full_name'),
        col('pi.is_contact_pi').alias('is_contact_pi')
    )

    # Extract Program Officers
    pos_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        explode_outer(col('program_officers')).alias('po')
    ).select(
        col('project_num'),
        col('fiscal_year'),
        lit('PO').alias('role_type'),
        lit(None).cast(LongType()).alias('profile_id'),
        col('po.first_name').alias('first_name'),
        col('po.middle_name').alias('middle_name'),
        col('po.last_name').alias('last_name'),
        col('po.full_name').alias('full_name'),
        lit(None).cast(BooleanType()).alias('is_contact_pi')
    )

    # Union and add surrogate key
    personnel_df = pis_df.union(pos_df).filter(col('full_name').isNotNull())

    personnel_df = personnel_df.select(
        md5(concat(
            col('project_num'),
            lit('_'),
            col('fiscal_year'),
            lit('_'),
            col('role_type'),
            lit('_'),
            coalesce(col('profile_id').cast(StringType()), col('full_name'))
        )).alias('personnel_key'),
        col('project_num'),
        col('fiscal_year'),
        col('role_type'),
        col('profile_id'),
        col('first_name'),
        col('middle_name'),
        col('last_name'),
        col('full_name'),
        col('is_contact_pi'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    )

    write_to_table(personnel_df, 'dim_personnel', ['personnel_key'])


def create_dim_study_sections(df: DataFrame):
    """Create/update dim_nih_study_sections dimension table."""
    study_sections_df = df.select(
        col('full_study_section.*')
    ).filter(col('srg_code').isNotNull()).dropDuplicates(['srg_code'])

    study_sections_df = study_sections_df.select(
        md5(col('srg_code')).alias('study_section_key'),
        col('srg_code'),
        col('srg_flex'),
        col('sra_designator_code'),
        col('sra_flex_code'),
        col('group_code'),
        col('name').alias('study_section_name'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    )

    write_to_table(study_sections_df, 'dim_study_sections', ['study_section_key'])


def create_dim_agencies(df: DataFrame):
    """Create/update dim_nih_agencies dimension table."""
    # Admin ICs
    admin_ics = df.select(
        col('agency_ic_admin.*'),
        lit('admin').alias('agency_type')
    ).filter(col('code').isNotNull())

    # Funding ICs
    funding_ics = df.select(
        explode_outer(col('agency_ic_fundings')).alias('ic'),
        lit('funding').alias('agency_type')
    ).select(
        col('ic.code').alias('code'),
        col('ic.abbreviation').alias('abbreviation'),
        col('ic.name').alias('name'),
        col('agency_type')
    ).filter(col('code').isNotNull())

    # Union and deduplicate
    agencies_df = admin_ics.union(funding_ics).dropDuplicates(['code', 'agency_type'])

    agencies_df = agencies_df.select(
        md5(concat(col('code'), lit('_'), col('agency_type'))).alias('agency_key'),
        col('code').alias('ic_code'),
        col('abbreviation').alias('ic_abbreviation'),
        col('name').alias('ic_name'),
        col('agency_type'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    )

    write_to_table(agencies_df, 'dim_agencies', ['agency_key'])


def create_fact_funding(df: DataFrame):
    """Create/update fact_nih_funding fact table."""
    # Create organization keys to join
    org_keys = df.select(
        col('project_num'),
        col('fiscal_year'),
        md5(concat(
            coalesce(col('organization.org_name'), lit('')),
            lit('_'),
            coalesce(col('organization.org_city'), lit('')),
            lit('_'),
            coalesce(col('organization.org_state'), lit(''))
        )).alias('org_key')
    )

    # Create admin IC keys
    admin_ic_keys = df.select(
        col('project_num'),
        col('fiscal_year'),
        md5(concat(col('agency_ic_admin.code'), lit('_admin'))).alias('admin_ic_key')
    )

    # Build fact table
    funding_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        col('award_amount'),
        col('direct_cost_amt'),
        col('indirect_cost_amt'),
        col('total_cost'),
        col('total_cost_sub_project'),
        to_date(col('budget_start')).alias('budget_start_date'),
        to_date(col('budget_end')).alias('budget_end_date'),
        to_date(col('award_notice_date')).alias('award_notice_date'),
        col('award_type'),
        col('arra_funded'),
        col('funding_mechanism'),
        col('cfda_code')
    )

    # Join with keys
    funding_df = funding_df.join(org_keys, ['project_num', 'fiscal_year'], 'left')
    funding_df = funding_df.join(admin_ic_keys, ['project_num', 'fiscal_year'], 'left')

    funding_df = funding_df.select(
        md5(concat(col('project_num'), lit('_'), col('fiscal_year'))).alias('funding_key'),
        col('project_num'),
        col('fiscal_year'),
        col('award_amount'),
        col('direct_cost_amt'),
        col('indirect_cost_amt'),
        col('total_cost'),
        col('total_cost_sub_project'),
        col('budget_start_date'),
        col('budget_end_date'),
        col('award_notice_date'),
        col('award_type'),
        col('arra_funded'),
        col('funding_mechanism'),
        col('cfda_code'),
        col('org_key'),
        col('admin_ic_key'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    )

    write_to_table(funding_df, 'fact_funding', ['project_num', 'fiscal_year'])


def create_bridge_publications(df: DataFrame):
    """Create/update bridge_nih_publications bridge table."""
    pubs_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        explode_outer(col('publications')).alias('pub')
    ).select(
        col('project_num'),
        col('fiscal_year'),
        col('pub.pmid').alias('pmid'),
        col('pub.pmc_id').alias('pmc_id'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    ).filter(col('pmid').isNotNull())

    write_to_table(pubs_df, 'bridge_publications', ['project_num', 'fiscal_year', 'pmid'])


def create_bridge_clinical_trials(df: DataFrame):
    """Create/update bridge_nih_clinical_trials bridge table."""
    trials_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        explode_outer(col('clinical_trials')).alias('trial')
    ).select(
        col('project_num'),
        col('fiscal_year'),
        col('trial.nct_id').alias('nct_id'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    ).filter(col('nct_id').isNotNull())

    write_to_table(trials_df, 'bridge_clinical_trials', ['project_num', 'fiscal_year', 'nct_id'])


def create_bridge_spending_categories(df: DataFrame):
    """Create/update bridge_nih_spending_categories bridge table."""
    categories_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        explode_outer(col('spending_categories')).alias('category')
    ).select(
        col('project_num'),
        col('fiscal_year'),
        col('category.name').alias('category_name'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    ).filter(col('category_name').isNotNull())

    write_to_table(categories_df, 'bridge_spending_categories', ['project_num', 'fiscal_year', 'category_name'])


def create_bridge_terms(df: DataFrame):
    """Create/update bridge_nih_terms bridge table."""
    # Terms can be an array of strings or a single string
    terms_df = df.select(
        col('project_num'),
        col('fiscal_year'),
        when(size(col('terms')) > 0, explode_outer(col('terms')))
        .otherwise(col('terms').cast(StringType())).alias('term_text')
    ).filter(col('term_text').isNotNull() & (trim(col('term_text')) != ''))

    terms_df = terms_df.select(
        col('project_num'),
        col('fiscal_year'),
        trim(col('term_text')).alias('term_text'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version')
    )

    write_to_table(terms_df, 'bridge_terms', ['project_num', 'fiscal_year', 'term_text'])


def write_to_table(df: DataFrame, table_key: str, merge_keys: List[str]):
    """
    Write DataFrame to silver table using merge (upsert).

    Args:
        df: DataFrame to write
        table_key: Key in SILVER_TABLES dict
        merge_keys: List of column names to use for matching
    """
    table_name = SILVER_TABLES[table_key]
    temp_view = f"temp_{table_key}"

    df.createOrReplaceTempView(temp_view)

    # Build merge condition
    merge_condition = " AND ".join([f"target.{key} = source.{key}" for key in merge_keys])

    # Get all columns except merge keys for UPDATE SET
    all_columns = df.columns
    update_columns = [col for col in all_columns if col not in merge_keys]
    update_set = ", ".join([f"{col} = source.{col}" for col in update_columns])

    # Build INSERT columns and values
    insert_columns = ", ".join(all_columns)
    insert_values = ", ".join([f"source.{col}" for col in all_columns])

    merge_sql = f"""
    MERGE INTO {table_name} target
    USING {temp_view} source
    ON {merge_condition}
    WHEN MATCHED THEN
        UPDATE SET {update_set}
    WHEN NOT MATCHED THEN
        INSERT ({insert_columns})
        VALUES ({insert_values})
    """

    print(f"Merging into {table_name}...")
    spark.sql(merge_sql)
    print(f"Merge completed for {table_name}")


if __name__ == "__main__":
    main()
