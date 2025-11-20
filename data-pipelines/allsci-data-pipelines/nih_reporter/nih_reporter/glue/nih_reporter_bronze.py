"""
NIH RePORTER Bronze Layer Glue Job

This Glue job reads raw JSONL files from the landing zone and writes them
to an Iceberg table in the bronze layer, preserving the complete raw structure.

The bronze layer serves as the immutable raw data store with no transformations
applied, capturing ALL fields from the API response.

Author: AllSci Data Pipeline
"""

import sys
from datetime import datetime
from typing import Dict, Any

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, input_file_name, lit, to_json, struct
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    ArrayType, LongType, TimestampType
)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'landing_zone_bucket',
    'bronze_bucket',
    'environment',
    'glue_database',
    'fiscal_years'  # Comma-separated list of fiscal years
])

# Initialize Spark and Glue contexts
sc = SparkContext()
glue_context = GlueContext(sc)
spark: SparkSession = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# Enable Iceberg support
spark.conf.set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", f"s3://{args['bronze_bucket']}/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")

# Job configuration
LANDING_ZONE_BUCKET = args['landing_zone_bucket']
BRONZE_BUCKET = args['bronze_bucket']
ENVIRONMENT = args['environment']
GLUE_DATABASE = args['glue_database']
FISCAL_YEARS = [int(fy.strip()) for fy in args['fiscal_years'].split(',')]
PIPELINE_VERSION = "1.0.0"

# Table configuration
BRONZE_TABLE_NAME = "nih_reporter_projects_bronze"
BRONZE_TABLE_FULL_NAME = f"glue_catalog.{GLUE_DATABASE}.{BRONZE_TABLE_NAME}"


def main():
    """Main execution function."""
    try:
        print(f"Starting Bronze layer job for fiscal years: {FISCAL_YEARS}")
        print(f"Environment: {ENVIRONMENT}")
        print(f"Landing zone: s3://{LANDING_ZONE_BUCKET}")
        print(f"Bronze zone: s3://{BRONZE_BUCKET}")

        # Create bronze table if it doesn't exist
        create_bronze_table_if_not_exists()

        # Process each fiscal year
        total_records = 0
        for fiscal_year in FISCAL_YEARS:
            print(f"Processing fiscal year: {fiscal_year}")
            records_processed = process_fiscal_year(fiscal_year)
            total_records += records_processed
            print(f"Processed {records_processed} records for FY{fiscal_year}")

        print(f"Bronze layer job completed successfully. Total records: {total_records}")
        job.commit()

    except Exception as e:
        print(f"Error in bronze layer job: {str(e)}")
        raise


def create_bronze_table_if_not_exists():
    """
    Create the bronze Iceberg table if it doesn't exist.

    The bronze table uses a flexible schema that can accommodate all fields
    from the NIH RePORTER API response.
    """
    # Check if table exists
    table_exists = spark.catalog._jcatalog.tableExists(GLUE_DATABASE, BRONZE_TABLE_NAME)

    if not table_exists:
        print(f"Creating bronze table: {BRONZE_TABLE_FULL_NAME}")

        # Create table with schema
        # Using a flexible approach: store the entire JSON as a string
        # plus extract key fields for partitioning and querying
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {BRONZE_TABLE_FULL_NAME} (
            -- Metadata fields
            source_file STRING COMMENT 'Source S3 file path',
            ingestion_timestamp TIMESTAMP COMMENT 'When data was ingested to landing zone',
            processing_timestamp TIMESTAMP COMMENT 'When data was processed to bronze',
            pipeline_version STRING COMMENT 'Pipeline version',

            -- Key identifiers (extracted for indexing/partitioning)
            fiscal_year INT COMMENT 'Fiscal year',
            project_num STRING COMMENT 'Project/grant number',
            appl_id BIGINT COMMENT 'Application ID',

            -- Complete raw record as JSON string
            raw_json STRING COMMENT 'Complete raw JSON record from API'
        )
        USING iceberg
        PARTITIONED BY (fiscal_year)
        LOCATION 's3://{BRONZE_BUCKET}/nih_reporter_projects/'
        TBLPROPERTIES (
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy',
            'format-version' = '2'
        )
        """

        spark.sql(create_table_sql)
        print(f"Created bronze table: {BRONZE_TABLE_FULL_NAME}")
    else:
        print(f"Bronze table already exists: {BRONZE_TABLE_FULL_NAME}")


def process_fiscal_year(fiscal_year: int) -> int:
    """
    Process all JSONL files for a specific fiscal year.

    Args:
        fiscal_year: Fiscal year to process

    Returns:
        Number of records processed
    """
    # Construct S3 path for this fiscal year
    s3_path = f"s3://{LANDING_ZONE_BUCKET}/nih_reporter/projects/projects_FY{fiscal_year}_*.jsonl"

    print(f"Reading data from: {s3_path}")

    try:
        # Read JSONL files
        # Use multiLine=false for JSONL format (one JSON object per line)
        df = spark.read.json(s3_path, multiLine=False)

        if df.count() == 0:
            print(f"No data found for fiscal year {fiscal_year}")
            return 0

        # Transform to bronze schema
        bronze_df = transform_to_bronze(df, fiscal_year)

        # Write to bronze table using Iceberg merge (upsert)
        write_to_bronze_table(bronze_df)

        record_count = bronze_df.count()
        return record_count

    except Exception as e:
        print(f"Error processing fiscal year {fiscal_year}: {str(e)}")
        # Check if files exist
        try:
            file_list = spark.sparkContext.wholeTextFiles(s3_path).take(1)
            if not file_list:
                print(f"No files found at {s3_path}")
        except:
            print(f"Unable to list files at {s3_path}")
        raise


def transform_to_bronze(df: DataFrame, fiscal_year: int) -> DataFrame:
    """
    Transform raw DataFrame to bronze schema.

    Args:
        df: Raw DataFrame from JSONL
        fiscal_year: Fiscal year being processed

    Returns:
        Transformed DataFrame
    """
    # Add metadata columns
    bronze_df = df.select(
        # Metadata
        input_file_name().alias('source_file'),
        col('_ingestion_metadata.ingestion_timestamp').cast(TimestampType()).alias('ingestion_timestamp'),
        current_timestamp().alias('processing_timestamp'),
        lit(PIPELINE_VERSION).alias('pipeline_version'),

        # Key identifiers (extracted for partitioning/querying)
        lit(fiscal_year).alias('fiscal_year'),
        col('project_num').cast(StringType()).alias('project_num'),
        col('appl_id').cast(LongType()).alias('appl_id'),

        # Complete raw record as JSON
        # Convert entire row to JSON string to preserve ALL fields
        to_json(struct(
            [col(field) for field in df.columns if not field.startswith('_ingestion_metadata')]
        )).alias('raw_json')
    )

    return bronze_df


def write_to_bronze_table(df: DataFrame):
    """
    Write DataFrame to bronze Iceberg table using merge (upsert).

    Uses Iceberg's MERGE INTO to handle updates to existing records
    while inserting new ones.

    Args:
        df: DataFrame to write
    """
    # Create a temporary view for the merge operation
    temp_view = "temp_bronze_data"
    df.createOrReplaceTempView(temp_view)

    # Execute merge operation
    # Match on project_num and fiscal_year to handle updates
    merge_sql = f"""
    MERGE INTO {BRONZE_TABLE_FULL_NAME} target
    USING {temp_view} source
    ON target.project_num = source.project_num
       AND target.fiscal_year = source.fiscal_year
       AND target.appl_id = source.appl_id
    WHEN MATCHED THEN
        UPDATE SET
            source_file = source.source_file,
            ingestion_timestamp = source.ingestion_timestamp,
            processing_timestamp = source.processing_timestamp,
            pipeline_version = source.pipeline_version,
            raw_json = source.raw_json
    WHEN NOT MATCHED THEN
        INSERT (
            source_file,
            ingestion_timestamp,
            processing_timestamp,
            pipeline_version,
            fiscal_year,
            project_num,
            appl_id,
            raw_json
        )
        VALUES (
            source.source_file,
            source.ingestion_timestamp,
            source.processing_timestamp,
            source.pipeline_version,
            source.fiscal_year,
            source.project_num,
            source.appl_id,
            source.raw_json
        )
    """

    print("Executing merge into bronze table...")
    spark.sql(merge_sql)
    print("Merge completed successfully")


if __name__ == "__main__":
    main()
