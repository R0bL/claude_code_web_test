from aws_cdk import (
    aws_glue as glue,
    aws_iam as iam,
)
from constructs import Construct


class GlueJobConstruct(Construct):
    def __init__(self, scope: Construct, id: str, environment: str):
        super().__init__(scope, id)

        ENV = environment

        # Reference existing shared IAM role (DO NOT CREATE NEW)
        self.glue_job_role = iam.Role.from_role_name(
            self,
            "GlueJobRole",
            role_name=f"allsci-{ENV}-glue-default-service-role"
        )

        # Bronze Glue Job
        self.glue_job_bronze = glue.CfnJob(
            self,
            "BronzeGlueJob",
            name=f"{ENV}_nih_reporter_bronze",
            description="NIH Reporter Bronze Glue Job",
            glue_version="5.0",
            job_mode="SCRIPT",
            role=self.glue_job_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                script_location=f"s3://aws-glue-assets-206250664027-us-east-1/cdk/{ENV}/nih_reporter/nih_reporter_bronze.py"
            ),
            default_arguments={
                "--job-bookmark-option": "job-bookmark-enable",
                "--TempDir": "s3://aws-glue-assets-206250664027-us-east-1/temporary/",
                "--enable-metrics": "true",
                "--datalake-formats": "iceberg",
                "--enable-auto-scaling": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--enable-glue-datacatalog": "true",
                "--enable-s3-parquet-optimized-committer": "true",
                "--additional-python-modules": "boto3,pandas,ujson",
                "--ENV": ENV,
            },
            connections=glue.CfnJob.ConnectionsListProperty(
                connections=[f"allsci-{ENV}-network"]
            ),
            worker_type="G.1X",
            number_of_workers=2,
            max_retries=0,
            timeout=20
        )

        # Silver Glue Job
        self.glue_job_silver = glue.CfnJob(
            self,
            "SilverGlueJob",
            name=f"{ENV}_nih_reporter_silver",
            description="NIH Reporter Silver Glue Job",
            glue_version="5.0",
            job_mode="SCRIPT",
            role=self.glue_job_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                script_location=f"s3://aws-glue-assets-206250664027-us-east-1/cdk/{ENV}/nih_reporter/nih_reporter_silver.py"
            ),
            default_arguments={
                "--extra-py-files": f"s3://aws-glue-assets-206250664027-us-east-1/cdk/{ENV}/nih_reporter/nih_reporter_glue_package.zip",
                "--TempDir": "s3://aws-glue-assets-206250664027-us-east-1/temporary/",
                "--enable-metrics": "true",
                "--datalake-formats": "iceberg",
                "--enable-auto-scaling": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--enable-glue-datacatalog": "true",
                "--enable-s3-parquet-optimized-committer": "true",
                "--job-bookmark-option": "job-bookmark-enable",
                "--additional-python-modules": "boto3,pandas,ujson",
                "--ENV": ENV,
            },
            connections=glue.CfnJob.ConnectionsListProperty(
                connections=[f"allsci-{ENV}-network"]
            ),
            number_of_workers=2,
            worker_type="G.1X",
            max_retries=0,
            timeout=180
        )

