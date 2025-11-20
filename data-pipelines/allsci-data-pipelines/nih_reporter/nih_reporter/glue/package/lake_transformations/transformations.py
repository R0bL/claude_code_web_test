from pyspark.sql.types import (
    StringType, StructType,
    StructField, LongType)
from pyspark.sql import Row, Window
import pyspark.sql.functions as F


def define_allsci_ids(spark, df, max_id_part, allsci_id_parts, prefix):
    """
    Generate AllSci IDs for new records.
    
    Args:
        spark: SparkSession
        df: DataFrame to add AllSci IDs to
        max_id_part: Maximum existing sequence number
        allsci_id_parts: List of column names to keep (e.g., ["allsci_id_numeric_part"])
        prefix: Prefix code for the entity type (e.g., "GR" for grants)
    
    Returns:
        DataFrame with allsci_id column added
    """
    df_rdd = df.rdd.zipWithIndex().map(lambda x: Row(**x[0].asDict(), row_index=x[1]))
    new_schema = StructType(df.schema.fields + [StructField("row_index", LongType(), False)])
    df = spark.createDataFrame(df_rdd, schema=new_schema)

    df = (
        df.withColumns({
            "allsci_id_part": (F.col("row_index") + F.lit(max_id_part) + 1).cast("long"),
            "allsci_id_time": F.unix_timestamp(F.current_timestamp())
        })
        .withColumn("sequence_padded", F.lpad(F.col("allsci_id_part").cast("string"), 13, "0"))
        .withColumn(
            "allsci_id",
            F.concat_ws("-", F.lit("ASC"), F.lit(prefix), F.col("sequence_padded"), F.lit("1.0"), F.col("allsci_id_time").cast("string"))
        )
        .drop("row_index", "sequence_padded")
    )
    
    # Rename allsci_id_part to allsci_id_numeric_part for consistency
    if "allsci_id_numeric_part" in allsci_id_parts:
        df = df.withColumnRenamed("allsci_id_part", "allsci_id_numeric_part")
    
    # Clean up temporary columns
    for id_part in ("allsci_id_part", "allsci_id_time"):
        if id_part not in allsci_id_parts and id_part in df.columns:
            df = df.drop(id_part)

    return df

