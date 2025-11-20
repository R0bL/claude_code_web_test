from datetime import datetime
import sys
import boto3
import json
import time

from pyspark.sql.window import Window
from pyspark.sql.functions import *
from pyspark.sql.types import *
import traceback

from pyspark.conf import SparkConf
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from lake_tools.transformations import CommonTransformations
from lake_tools.catalogs import TransformationCatalog
from utils.functions import (
    read_json_from_s3,
    update_flag
)

# Get job parameters - following AllSci convention-based naming
triggered_by_workflow = True
try:
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'ENV', 'FISCAL_YEARS'])
    print("Job triggered by StepFunctions")
except:
    triggered_by_workflow = False
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'ENV'])
    args["FISCAL_YEARS"] = "2024,2023"

# Constants and Configurations
ENV = args['ENV']
FISCAL_YEARS = args['FISCAL_YEARS']
LANDING_ZONE_BUCKET = f"allsci-landingzone-{ENV}"
BRONZE_DATABASE = f"allsci_{ENV}_nih_reporter_bronze"
SILVER_DATABASE = f"allsci_{ENV}_nih_reporter_silver"

scf = SparkConf()
scf.setAll([
    ('spark.sql.extensions', 'org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions'),
    ('spark.sql.catalog.glue_catalog', 'org.apache.iceberg.spark.SparkCatalog'),
    ('spark.sql.catalog.glue_catalog.warehouse', f's3://allsci-silver-{ENV}/'),
    ('spark.sql.catalog.glue_catalog.catalog-impl', 'org.apache.iceberg.aws.glue.GlueCatalog'),
    ('spark.sql.catalog.glue_catalog.io-impl', 'org.apache.iceberg.aws.s3.S3FileIO'),
    ('spark.sql.defaultCatalog', 'glue_catalog'),
    # Optimize S3 I/O
    ('spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version', '2'),
    ('spark.speculation', 'true'),
])

sc = SparkContext(conf=scf)
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

##################################### JOB INIT #####################################

# Set fiscal years to process
if triggered_by_workflow:
    fiscal_years_to_process = json.loads(FISCAL_YEARS) if isinstance(FISCAL_YEARS, str) and FISCAL_YEARS.startswith('[') else [int(fy.strip()) for fy in FISCAL_YEARS.split(',')]
else:
    fiscal_years_to_process = [int(fy.strip()) for fy in FISCAL_YEARS.split(',')]

print(f"Processing fiscal years: {','.join(map(str, fiscal_years_to_process))}")

# Read from bronze layer
df_bronze = (
    spark.read.table(f"{BRONZE_DATABASE}.projects_metadata")
    .filter(col("fiscal_year").isin(fiscal_years_to_process))
    .select("project_num", "fiscal_year", "data_object", "source_date")
)

print(f"Read {df_bronze.count()} records from bronze layer")

# Remove duplicates based on project_num and fiscal_year (latest source_date)
window_spec = Window.partitionBy("project_num", "fiscal_year").orderBy(col("source_date").desc())

df_bronze = (
    df_bronze
    .withColumn("row_num", row_number().over(window_spec))
    .filter(col("row_num") == 1)
    .drop("row_num")
)

print(f"After deduplication: {df_bronze.count()} records")

common_transf = CommonTransformations()

# Process each silver table using TransformationCatalog
for table in (
    "nih_reporter_projects",
    "nih_reporter_organizations",
    "nih_reporter_principal_investigators",
    "nih_reporter_program_officers",
    "nih_reporter_publications",
    "nih_reporter_clinical_trials",
    "nih_reporter_agencies_admin",
    "nih_reporter_agencies_funding",
    "nih_reporter_spending_categories",
    "nih_reporter_terms",
    "nih_reporter_study_sections",
):

    try:
        print(f"\n{'='*60}")
        print(f"Processing table: {table}")
        print(f"{'='*60}")

        transformer = TransformationCatalog()[table]

        # Parse data from bronze
        df_upsert = transformer.parse(df_bronze, 'data_object')
        print(f"Parsed {df_upsert.count()} rows")

        # Apply type casting
        df_upsert = common_transf.casting(df_upsert, transformer.casting_schema)

        # Parse date columns
        df_upsert = common_transf.define_date_columns(df_upsert, transformer.date_columns)

        # Set ingestion datetime
        df_upsert = common_transf.set_ingestion_datetime(df_upsert)

        # Select final columns
        df_upsert = common_transf.select_columns(df_upsert, transformer.casting_schema, transformer.extra_columns)

        # Filter duplicates within the batch
        df_upsert = common_transf.filter_duplicates(df_upsert, transformer.merge_conditions, "source_date")

        print(f"Final row count for upsert: {df_upsert.count()}")

        # Create temp view for MERGE
        df_upsert.createOrReplaceTempView("upsert_batch")

        # Execute MERGE INTO
        merge_sql = f"""
        MERGE INTO {SILVER_DATABASE}.{table} AS target
            USING upsert_batch AS source
            ON 
                {" AND ".join([f"COALESCE(target.{_id}, 'NULL') = COALESCE(source.{_id}, 'NULL')" for _id in transformer.merge_conditions])}
            WHEN MATCHED AND (source.source_date > target.source_date) THEN
                UPDATE SET *
            WHEN NOT MATCHED THEN
                INSERT *
        """

        spark.sql(merge_sql)
        print(f"Data successfully written to silver layer table {table}")
        time.sleep(2)

    except Exception as e:
        print(f"Error processing table {table}: {str(e)}")
        traceback.print_exc()
        raise

print("\nUpdating NIH Reporter silver flag file...")
try:
    silver_flag = read_json_from_s3(
        LANDING_ZONE_BUCKET,
        "control_flags/silver/nih_reporter/flag.json"
    )
    silver_flag['batch_to_process'] = fiscal_years_to_process
    silver_flag['last_processed_timestamp'] = datetime.utcnow().isoformat()
    
    update_flag(LANDING_ZONE_BUCKET, silver_flag, ["nih_reporter"])
    print("Silver flag updated successfully")
except Exception as e:
    print(f"Warning: Could not update silver flag: {str(e)}")
    # Don't fail the job if flag update fails

##################################### JOB END #####################################
print("\nSilver layer job completed successfully!")
job.commit()
