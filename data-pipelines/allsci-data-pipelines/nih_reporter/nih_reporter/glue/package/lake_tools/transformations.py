from pyspark.sql.window import Window
from pyspark.sql import Row
from pyspark.sql.types import *
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    BooleanType, IntegerType, DoubleType, ArrayType, DateType)
from pyspark.sql.functions import *
from pyspark.sql.functions import (
    from_json, to_json, col, lit, when, date_format, to_timestamp, row_number,
    unix_timestamp, current_timestamp, coalesce, to_utc_timestamp, lpad, concat_ws,
    explode_outer, sha2, concat, md5, trim)


class CommonTransformations:

    def casting(self, df, schema, skip_columns=[]):
        for col_name in [field.name for field in schema if field.name not in skip_columns]:
            df = df.withColumn(
                col_name,
                coalesce(col(col_name), lit(None)).cast(schema[col_name].dataType)
            )

        return df

    def select_columns(self, df, columns, extra_cols=[]):

        if isinstance(columns, StructType):
            cols = [field.name for field in columns.fields]
            return df.select(*(cols + extra_cols))

        if isinstance(columns, list):
            return df.select(*(columns + extra_cols))

        else:
            raise ValueError("Columns must be a list or a string representing SQL expression.")

    def set_ingestion_datetime(self, df):
        return df.withColumn("ingestion_datetime", to_utc_timestamp(current_timestamp(), "UTC"))

    def define_date_columns(self, df, date_columns):

        for date_column in date_columns:
            df = df.withColumn(date_column,
                               date_format(
                                   when(
                                       to_timestamp(col(date_column), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS").isNotNull(),
                                       to_timestamp(col(date_column), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS")
                                   ).when(
                                       to_timestamp(col(date_column), "yyyy-MM-dd'T'HH:mm:ss").isNotNull(),
                                       to_timestamp(col(date_column), "yyyy-MM-dd'T'HH:mm:ss")
                                   ).otherwise(
                                       to_timestamp(col(date_column), "yyyy-MM-dd")
                                   ),
                                   "yyyy-MM-dd"
                               ).cast("date")
                               )

        return df

    def filter_duplicates(self, df, partition_columns, order_column):

        filter_window = (
            Window
            .partitionBy([
                col(column_name) for column_name in partition_columns
            ])
            .orderBy(col(order_column).desc())
        )

        filtered_df = (
            df
            .withColumn("filter_row_num", row_number().over(filter_window))
            .filter(col("filter_row_num") == 1)
            .drop("filter_row_num")
        )

        return filtered_df


class NihReporterProjects:
    """Main NIH Reporter projects table."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_projects"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
            "project_start_date",
            "project_end_date",
            "budget_start_date",
            "budget_end_date",
            "award_notice_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("appl_id", LongType()),
            StructField("subproject_id", StringType()),
            StructField("project_serial_num", StringType()),
            StructField("core_project_num", StringType()),
            StructField("activity_code", StringType()),
            StructField("project_title", StringType()),
            StructField("project_start_date", DateType()),
            StructField("project_end_date", DateType()),
            StructField("budget_start_date", DateType()),
            StructField("budget_end_date", DateType()),
            StructField("award_notice_date", DateType()),
            StructField("award_type", StringType()),
            StructField("award_amount", LongType()),
            StructField("direct_cost_amt", LongType()),
            StructField("indirect_cost_amt", LongType()),
            StructField("total_cost", LongType()),
            StructField("total_cost_sub_project", LongType()),
            StructField("abstract_text", StringType()),
            StructField("phr_text", StringType()),
            StructField("project_detail_url", StringType()),
            StructField("contact_pi_name", StringType()),
            StructField("publication_count", IntegerType()),
            StructField("arra_funded", StringType()),
            StructField("funding_mechanism", StringType()),
            StructField("cfda_code", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,appl_id:bigint,subproject_id:string,project_serial_num:string,core_project_num:string,activity_code:string,project_title:string,project_start_date:string,project_end_date:string,budget_start:string,budget_end:string,award_notice_date:string,award_type:string,award_amount:bigint,direct_cost_amt:bigint,indirect_cost_amt:bigint,total_cost:bigint,total_cost_sub_project:bigint,abstract_text:string,phr_text:string,project_detail_url:string,contact_pi_name:string,publication_count:int,arra_funded:string,funding_mechanism:string,cfda_code:string>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            col("parsed.appl_id").alias("appl_id"),
            col("parsed.subproject_id").alias("subproject_id"),
            col("parsed.project_serial_num").alias("project_serial_num"),
            col("parsed.core_project_num").alias("core_project_num"),
            col("parsed.activity_code").alias("activity_code"),
            col("parsed.project_title").alias("project_title"),
            col("parsed.project_start_date").alias("project_start_date"),
            col("parsed.project_end_date").alias("project_end_date"),
            col("parsed.budget_start").alias("budget_start_date"),
            col("parsed.budget_end").alias("budget_end_date"),
            col("parsed.award_notice_date").alias("award_notice_date"),
            col("parsed.award_type").alias("award_type"),
            col("parsed.award_amount").alias("award_amount"),
            col("parsed.direct_cost_amt").alias("direct_cost_amt"),
            col("parsed.indirect_cost_amt").alias("indirect_cost_amt"),
            col("parsed.total_cost").alias("total_cost"),
            col("parsed.total_cost_sub_project").alias("total_cost_sub_project"),
            col("parsed.abstract_text").alias("abstract_text"),
            col("parsed.phr_text").alias("phr_text"),
            col("parsed.project_detail_url").alias("project_detail_url"),
            col("parsed.contact_pi_name").alias("contact_pi_name"),
            col("parsed.publication_count").alias("publication_count"),
            col("parsed.arra_funded").alias("arra_funded"),
            col("parsed.funding_mechanism").alias("funding_mechanism"),
            col("parsed.cfda_code").alias("cfda_code"),
            col("source_date")
        )

        return df


class NihReporterOrganizations:
    """NIH Reporter organizations table."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_organizations"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "org_key",
        ]

        self.casting_schema = StructType([
            StructField("org_key", StringType()),
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("org_name", StringType()),
            StructField("org_city", StringType()),
            StructField("org_state", StringType()),
            StructField("org_state_name", StringType()),
            StructField("org_country", StringType()),
            StructField("org_zipcode", StringType()),
            StructField("org_fips", StringType()),
            StructField("dept_type", StringType()),
            StructField("org_duns", StringType()),
            StructField("org_uei", StringType()),
            StructField("org_ipf_code", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,organization:struct<org_name:string,org_city:string,org_state:string,org_state_name:string,org_country:string,org_zipcode:string,org_fips:string,dept_type:string,org_duns:string,org_uei:string,org_ipf_code:string>>"))

        df = df.select(
            md5(concat(
                coalesce(col("parsed.organization.org_name"), lit('')),
                lit('_'),
                coalesce(col("parsed.organization.org_city"), lit('')),
                lit('_'),
                coalesce(col("parsed.organization.org_state"), lit(''))
            )).alias("org_key"),
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            col("parsed.organization.org_name").alias("org_name"),
            col("parsed.organization.org_city").alias("org_city"),
            col("parsed.organization.org_state").alias("org_state"),
            col("parsed.organization.org_state_name").alias("org_state_name"),
            col("parsed.organization.org_country").alias("org_country"),
            col("parsed.organization.org_zipcode").alias("org_zipcode"),
            col("parsed.organization.org_fips").alias("org_fips"),
            col("parsed.organization.dept_type").alias("dept_type"),
            col("parsed.organization.org_duns").alias("org_duns"),
            col("parsed.organization.org_uei").alias("org_uei"),
            col("parsed.organization.org_ipf_code").alias("org_ipf_code"),
            col("source_date")
        ).filter(col("org_name").isNotNull())

        return df


class NihReporterPrincipalInvestigators:
    """NIH Reporter principal investigators table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_principal_investigators"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "profile_id",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("profile_id", LongType()),
            StructField("first_name", StringType()),
            StructField("middle_name", StringType()),
            StructField("last_name", StringType()),
            StructField("full_name", StringType()),
            StructField("is_contact_pi", BooleanType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,principal_investigators:array<struct<profile_id:bigint,first_name:string,middle_name:string,last_name:string,full_name:string,is_contact_pi:boolean>>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.principal_investigators")).alias("pi"),
            col("source_date")
        ).select(
            col("project_num"),
            col("fiscal_year"),
            col("pi.profile_id").alias("profile_id"),
            col("pi.first_name").alias("first_name"),
            col("pi.middle_name").alias("middle_name"),
            col("pi.last_name").alias("last_name"),
            col("pi.full_name").alias("full_name"),
            col("pi.is_contact_pi").alias("is_contact_pi"),
            col("source_date")
        ).filter(col("profile_id").isNotNull())

        return df


class NihReporterProgramOfficers:
    """NIH Reporter program officers table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_program_officers"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "full_name",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("first_name", StringType()),
            StructField("middle_name", StringType()),
            StructField("last_name", StringType()),
            StructField("full_name", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,program_officers:array<struct<first_name:string,middle_name:string,last_name:string,full_name:string>>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.program_officers")).alias("po"),
            col("source_date")
        ).select(
            col("project_num"),
            col("fiscal_year"),
            col("po.first_name").alias("first_name"),
            col("po.middle_name").alias("middle_name"),
            col("po.last_name").alias("last_name"),
            col("po.full_name").alias("full_name"),
            col("source_date")
        ).filter(col("full_name").isNotNull())

        return df


class NihReporterPublications:
    """NIH Reporter publications table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_publications"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "pmid",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("pmid", LongType()),
            StructField("pmc_id", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,publications:array<struct<pmid:bigint,pmc_id:string>>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.publications")).alias("pub"),
            col("source_date")
        ).select(
            col("project_num"),
            col("fiscal_year"),
            col("pub.pmid").alias("pmid"),
            col("pub.pmc_id").alias("pmc_id"),
            col("source_date")
        ).filter(col("pmid").isNotNull())

        return df


class NihReporterClinicalTrials:
    """NIH Reporter clinical trials table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_clinical_trials"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "nct_id",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("nct_id", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,clinical_trials:array<struct<nct_id:string>>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.clinical_trials")).alias("ct"),
            col("source_date")
        ).select(
            col("project_num"),
            col("fiscal_year"),
            col("ct.nct_id").alias("nct_id"),
            col("source_date")
        ).filter(col("nct_id").isNotNull())

        return df


class NihReporterAgenciesAdmin:
    """NIH Reporter admin agencies table."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_agencies_admin"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("ic_code", StringType()),
            StructField("ic_abbreviation", StringType()),
            StructField("ic_name", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,agency_ic_admin:struct<code:string,abbreviation:string,name:string>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            col("parsed.agency_ic_admin.code").alias("ic_code"),
            col("parsed.agency_ic_admin.abbreviation").alias("ic_abbreviation"),
            col("parsed.agency_ic_admin.name").alias("ic_name"),
            col("source_date")
        ).filter(col("ic_code").isNotNull())

        return df


class NihReporterAgenciesFunding:
    """NIH Reporter funding agencies table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_agencies_funding"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "ic_code",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("ic_code", StringType()),
            StructField("ic_abbreviation", StringType()),
            StructField("ic_name", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,agency_ic_fundings:array<struct<code:string,abbreviation:string,name:string>>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.agency_ic_fundings")).alias("ic"),
            col("source_date")
        ).select(
            col("project_num"),
            col("fiscal_year"),
            col("ic.code").alias("ic_code"),
            col("ic.abbreviation").alias("ic_abbreviation"),
            col("ic.name").alias("ic_name"),
            col("source_date")
        ).filter(col("ic_code").isNotNull())

        return df


class NihReporterSpendingCategories:
    """NIH Reporter spending categories table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_spending_categories"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "category_name",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("category_name", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,spending_categories:array<struct<name:string>>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.spending_categories")).alias("cat"),
            col("source_date")
        ).select(
            col("project_num"),
            col("fiscal_year"),
            col("cat.name").alias("category_name"),
            col("source_date")
        ).filter(col("category_name").isNotNull())

        return df


class NihReporterTerms:
    """NIH Reporter research terms table (exploded from array)."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_terms"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
            "term_text",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("term_text", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,terms:array<string>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            explode_outer(col("parsed.terms")).alias("term_text"),
            col("source_date")
        ).filter(col("term_text").isNotNull())

        return df


class NihReporterStudySections:
    """NIH Reporter study sections table."""

    def __init__(self, **kwargs):
        self.table_name = "nih_reporter_study_sections"

        self.extra_columns = [
            'ingestion_datetime',
            "source_date",
        ]

        self.date_columns = [
            "source_date",
        ]

        self.merge_conditions = [
            "project_num",
            "fiscal_year",
        ]

        self.casting_schema = StructType([
            StructField("project_num", StringType()),
            StructField("fiscal_year", IntegerType()),
            StructField("srg_code", StringType()),
            StructField("srg_flex", StringType()),
            StructField("sra_designator_code", StringType()),
            StructField("sra_flex_code", StringType()),
            StructField("group_code", StringType()),
            StructField("study_section_name", StringType()),
        ])

    def parse(self, df, raw_object_column):
        df = df.withColumn("parsed", from_json(col(raw_object_column), "struct<project_num:string,fiscal_year:int,full_study_section:struct<srg_code:string,srg_flex:string,sra_designator_code:string,sra_flex_code:string,group_code:string,name:string>>"))

        df = df.select(
            col("parsed.project_num").alias("project_num"),
            col("parsed.fiscal_year").alias("fiscal_year"),
            col("parsed.full_study_section.srg_code").alias("srg_code"),
            col("parsed.full_study_section.srg_flex").alias("srg_flex"),
            col("parsed.full_study_section.sra_designator_code").alias("sra_designator_code"),
            col("parsed.full_study_section.sra_flex_code").alias("sra_flex_code"),
            col("parsed.full_study_section.group_code").alias("group_code"),
            col("parsed.full_study_section.name").alias("study_section_name"),
            col("source_date")
        ).filter(col("srg_code").isNotNull())

        return df
