"""
NIH RePORTER Bronze Layer Glue Job

This Glue job reads raw JSONL files from the landing zone and writes them
to an Iceberg table in the bronze layer, preserving the complete raw structure.

The bronze layer serves as the immutable raw data store with no transformations
applied, capturing ALL fields from the API response.

Author: AllSci Data Pipeline
"""

import sys
import json
from datetime import datetime
from typing import Dict, Any

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    col, current_timestamp, input_file_name, lit, from_json,
    regexp_extract, to_date
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DateType,
    ArrayType, LongType, TimestampType
)

from utils.functions import (
    read_json_from_s3,
    write_json_to_s3
)

# Get job parameters - following AllSci convention-based naming
try:
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'ENV', 'FISCAL_YEARS'])
    params_from_workflow = True
except:
    # Fallback for manual runs
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'ENV'])
    args['FISCAL_YEARS'] = '2024,2023'
    params_from_workflow = False

# Initialize Spark and Glue contexts
sc = SparkContext()
glue_context = GlueContext(sc)
spark: SparkSession = glue_context.spark_session
job = Job(glue_context)
job.init(args['JOB_NAME'], args)

# Job configuration using convention-based naming
ENV = args['ENV']
LANDING_ZONE_BUCKET = f"allsci-landingzone-{ENV}"
BRONZE_BUCKET = f"allsci-bronze-{ENV}"
GLUE_DATABASE = f"allsci_{ENV}_nih_reporter_bronze"
FISCAL_YEARS = [int(fy.strip()) for fy in args['FISCAL_YEARS'].split(',')]
PIPELINE_VERSION = "1.0.0"

# Enable Iceberg support
spark.conf.set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
spark.conf.set("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.warehouse", f"s3://{BRONZE_BUCKET}/")
spark.conf.set("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
spark.conf.set("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")

# Table configuration
BRONZE_TABLE_NAME = "projects_metadata"
BRONZE_TABLE_FULL_NAME = f"glue_catalog.{GLUE_DATABASE}.{BRONZE_TABLE_NAME}"


def main():
    """Main execution function."""
    try:
        print(f"Starting Bronze layer job for fiscal years: {FISCAL_YEARS}")
        print(f"Environment: {ENV}")
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
        
        # Update bronze control flag
        print("\nUpdating NIH Reporter bronze flag file...")
        try:
            bronze_flag = read_json_from_s3(
                LANDING_ZONE_BUCKET,
                "control_flags/bronze/nih_reporter/flag.json"
            )
            if bronze_flag is None:
                # Create initial flag structure
                bronze_flag = {
                    "job_name": "nih_reporter",
                    "source_layer": "landing",
                    "target_layer": "bronze",
                    "batch_to_process": FISCAL_YEARS,
                    "sources_last_updated_at": {}
                }
            else:
                bronze_flag['batch_to_process'] = FISCAL_YEARS
            
            bronze_flag['last_updated_at'] = datetime.utcnow().isoformat()
            
            write_json_to_s3(
                bronze_flag,
                LANDING_ZONE_BUCKET,
                "control_flags/bronze/nih_reporter/flag.json"
            )
            print("Bronze flag updated successfully")
        except Exception as e:
            print(f"Warning: Could not update bronze flag: {str(e)}")
            # Don't fail the job if flag update fails
        
        job.commit()

    except Exception as e:
        print(f"Error in bronze layer job: {str(e)}")
        raise


def create_bronze_table_if_not_exists():
    """
    Create the bronze Iceberg table if it doesn't exist.

    The bronze table stores minimal metadata with the complete raw JSON object,
    following the AllSci pattern for bronze layer tables.
    """
    # Check if table exists
    table_exists = spark.catalog._jcatalog.tableExists(GLUE_DATABASE, BRONZE_TABLE_NAME)

    if not table_exists:
        print(f"Creating bronze table: {BRONZE_TABLE_FULL_NAME}")

        # Create table with simplified schema following AllSci pattern
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {BRONZE_TABLE_FULL_NAME} (
            project_num STRING COMMENT 'Project/grant number (natural key)',
            fiscal_year INT COMMENT 'Fiscal year for partitioning',
            data_object STRING COMMENT 'Complete raw JSON data from API',
            source_date DATE COMMENT 'Date when data was extracted from API',
            ingestion_datetime TIMESTAMP COMMENT 'Timestamp when data was ingested into bronze'
        )
        USING iceberg
        PARTITIONED BY (fiscal_year)
        LOCATION 's3://{BRONZE_BUCKET}/nih_reporter/projects_metadata'
        TBLPROPERTIES (
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'zstd',
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
        # Read JSONL files as text
        df = spark.read.text(s3_path)

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
    Transform raw JSONL text to bronze schema.

    Args:
        df: Raw DataFrame with 'value' column containing JSONL text
        fiscal_year: Fiscal year being processed

    Returns:
        Transformed DataFrame following AllSci bronze pattern
    """
    # Parse the JSON to extract project_num for indexing
    from pyspark.sql.types import StructType, StructField
    
    # Define minimal schema to extract project_num
    schema = StructType([
        StructField("project_num", StringType(), True)
    ])
    
    # Extract source_date from filename (format: projects_FY2024_YYYY-MM-DD_batch*.jsonl)
    bronze_df = df.select(
        input_file_name().alias('filename'),
        col('value').alias('data_object')
    ).withColumn(
        'source_date_str', 
        regexp_extract('filename', r'_(\d{4}-\d{2}-\d{2})_', 1)
    ).withColumn(
        'source_date',
        to_date('source_date_str')
    ).withColumn(
        'parsed',
        from_json(col('data_object'), schema)
    ).select(
        col('parsed.project_num').alias('project_num'),
        lit(fiscal_year).alias('fiscal_year'),
        col('data_object'),
        col('source_date'),
        current_timestamp().alias('ingestion_datetime')
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
    WHEN MATCHED AND source.source_date > target.source_date THEN
        UPDATE SET
            data_object = source.data_object,
            source_date = source.source_date,
            ingestion_datetime = source.ingestion_datetime
    WHEN NOT MATCHED THEN
        INSERT (
            project_num,
            fiscal_year,
            data_object,
            source_date,
            ingestion_datetime
        )
        VALUES (
            source.project_num,
            source.fiscal_year,
            source.data_object,
            source.source_date,
            source.ingestion_datetime
        )
    """

    print("Executing merge into bronze table...")
    spark.sql(merge_sql)
    print("Merge completed successfully")


if __name__ == "__main__":
    main()
