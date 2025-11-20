"""
NIH RePORTER CDK Stack

This stack defines all AWS infrastructure for the NIH RePORTER data pipeline:
- Lambda function for API ingestion
- Glue jobs for bronze and silver transformations
- Step Functions workflow for orchestration
- EventBridge scheduler for periodic execution
- IAM roles and policies

Author: AllSci Data Pipeline
"""

from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_glue as glue,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
from typing import Dict, Any


class NIHReporterStack(Stack):
    """
    CDK Stack for NIH RePORTER data pipeline.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        landing_zone_bucket_name: str,
        bronze_bucket_name: str,
        silver_bucket_name: str,
        glue_database_name: str,
        **kwargs
    ) -> None:
        """
        Initialize the NIH RePORTER stack.

        Args:
            scope: CDK scope
            construct_id: Construct ID
            environment: Environment (dev/prod)
            landing_zone_bucket_name: S3 bucket for landing zone
            bronze_bucket_name: S3 bucket for bronze layer
            silver_bucket_name: S3 bucket for silver layer
            glue_database_name: Glue catalog database name
            **kwargs: Additional stack arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment = environment
        self.landing_zone_bucket_name = landing_zone_bucket_name
        self.bronze_bucket_name = bronze_bucket_name
        self.silver_bucket_name = silver_bucket_name
        self.glue_database_name = glue_database_name

        # Reference existing S3 buckets
        self.landing_zone_bucket = s3.Bucket.from_bucket_name(
            self, 'LandingZoneBucket',
            bucket_name=landing_zone_bucket_name
        )

        self.bronze_bucket = s3.Bucket.from_bucket_name(
            self, 'BronzeBucket',
            bucket_name=bronze_bucket_name
        )

        self.silver_bucket = s3.Bucket.from_bucket_name(
            self, 'SilverBucket',
            bucket_name=silver_bucket_name
        )

        # Create Lambda function for API ingestion
        self.ingestion_lambda = self._create_ingestion_lambda()

        # Create Glue jobs
        self.bronze_glue_job = self._create_bronze_glue_job()
        self.silver_glue_job = self._create_silver_glue_job()

        # Create Step Functions workflow
        self.state_machine = self._create_state_machine()

        # Create EventBridge scheduler
        self.scheduler = self._create_scheduler()

        # Outputs
        self._create_outputs()

    def _create_ingestion_lambda(self) -> lambda_.Function:
        """
        Create Lambda function for NIH RePORTER API ingestion.

        Returns:
            Lambda function
        """
        # Create Lambda execution role
        lambda_role = iam.Role(
            self, 'NIHReporterLambdaRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSLambdaBasicExecutionRole'
                )
            ],
            role_name=f'nih-reporter-lambda-role-{self.environment}'
        )

        # Grant S3 write permissions to landing zone
        self.landing_zone_bucket.grant_write(lambda_role)

        # Create Lambda function
        ingestion_function = lambda_.Function(
            self, 'NIHReporterIngestionLambda',
            function_name=f'nih-reporter-ingestion-{self.environment}',
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.lambda_handler',
            code=lambda_.Code.from_asset('nih_reporter/lambda_function'),
            role=lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                'LANDING_ZONE_BUCKET': self.landing_zone_bucket_name,
                'API_BASE_URL': 'https://api.reporter.nih.gov',
                'RATE_LIMIT_DELAY': '1.0',
                'MAX_RECORDS_PER_REQUEST': '500',
                'MAX_OFFSET': '14999',
                'ENVIRONMENT': self.environment
            },
            description='Ingests NIH RePORTER project data from API to S3'
        )

        return ingestion_function

    def _create_bronze_glue_job(self) -> glue.CfnJob:
        """
        Create Glue job for bronze layer processing.

        Returns:
            Glue job
        """
        # Create Glue job role
        glue_role = iam.Role(
            self, 'NIHReporterBronzeGlueRole',
            assumed_by=iam.ServicePrincipal('glue.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSGlueServiceRole'
                )
            ],
            role_name=f'nih-reporter-bronze-glue-role-{self.environment}'
        )

        # Grant S3 permissions
        self.landing_zone_bucket.grant_read(glue_role)
        self.bronze_bucket.grant_read_write(glue_role)

        # Grant Glue catalog permissions
        glue_role.add_to_policy(iam.PolicyStatement(
            actions=[
                'glue:GetDatabase',
                'glue:GetTable',
                'glue:GetTables',
                'glue:CreateTable',
                'glue:UpdateTable',
                'glue:DeleteTable',
                'glue:BatchCreatePartition',
                'glue:BatchDeletePartition',
                'glue:GetPartition',
                'glue:GetPartitions'
            ],
            resources=[
                f'arn:aws:glue:{self.region}:{self.account}:catalog',
                f'arn:aws:glue:{self.region}:{self.account}:database/{self.glue_database_name}',
                f'arn:aws:glue:{self.region}:{self.account}:table/{self.glue_database_name}/*'
            ]
        ))

        # Create Glue job
        bronze_job = glue.CfnJob(
            self, 'NIHReporterBronzeGlueJob',
            name=f'nih-reporter-bronze-{self.environment}',
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name='glueetl',
                python_version='3',
                script_location=f's3://{self.bronze_bucket_name}/glue-scripts/nih_reporter_bronze.py'
            ),
            glue_version='4.0',
            max_retries=1,
            timeout=2880,  # 48 hours
            number_of_workers=10,
            worker_type='G.1X',
            default_arguments={
                '--enable-metrics': 'true',
                '--enable-spark-ui': 'true',
                '--enable-job-insights': 'true',
                '--enable-glue-datacatalog': 'true',
                '--enable-continuous-cloudwatch-log': 'true',
                '--job-language': 'python',
                '--TempDir': f's3://{self.bronze_bucket_name}/glue-temp/',
                '--spark-event-logs-path': f's3://{self.bronze_bucket_name}/glue-spark-logs/',
                '--landing_zone_bucket': self.landing_zone_bucket_name,
                '--bronze_bucket': self.bronze_bucket_name,
                '--environment': self.environment,
                '--glue_database': self.glue_database_name,
                '--datalake-formats': 'iceberg'
            },
            description='Processes NIH RePORTER raw data into bronze layer Iceberg tables'
        )

        return bronze_job

    def _create_silver_glue_job(self) -> glue.CfnJob:
        """
        Create Glue job for silver layer processing.

        Returns:
            Glue job
        """
        # Create Glue job role
        glue_role = iam.Role(
            self, 'NIHReporterSilverGlueRole',
            assumed_by=iam.ServicePrincipal('glue.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    'service-role/AWSGlueServiceRole'
                )
            ],
            role_name=f'nih-reporter-silver-glue-role-{self.environment}'
        )

        # Grant S3 permissions
        self.bronze_bucket.grant_read(glue_role)
        self.silver_bucket.grant_read_write(glue_role)

        # Grant Glue catalog permissions
        glue_role.add_to_policy(iam.PolicyStatement(
            actions=[
                'glue:GetDatabase',
                'glue:GetTable',
                'glue:GetTables',
                'glue:CreateTable',
                'glue:UpdateTable',
                'glue:DeleteTable',
                'glue:BatchCreatePartition',
                'glue:BatchDeletePartition',
                'glue:GetPartition',
                'glue:GetPartitions'
            ],
            resources=[
                f'arn:aws:glue:{self.region}:{self.account}:catalog',
                f'arn:aws:glue:{self.region}:{self.account}:database/{self.glue_database_name}',
                f'arn:aws:glue:{self.region}:{self.account}:table/{self.glue_database_name}/*'
            ]
        ))

        # Create Glue job
        silver_job = glue.CfnJob(
            self, 'NIHReporterSilverGlueJob',
            name=f'nih-reporter-silver-{self.environment}',
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name='glueetl',
                python_version='3',
                script_location=f's3://{self.silver_bucket_name}/glue-scripts/nih_reporter_silver.py'
            ),
            glue_version='4.0',
            max_retries=1,
            timeout=2880,  # 48 hours
            number_of_workers=20,
            worker_type='G.2X',
            default_arguments={
                '--enable-metrics': 'true',
                '--enable-spark-ui': 'true',
                '--enable-job-insights': 'true',
                '--enable-glue-datacatalog': 'true',
                '--enable-continuous-cloudwatch-log': 'true',
                '--job-language': 'python',
                '--TempDir': f's3://{self.silver_bucket_name}/glue-temp/',
                '--spark-event-logs-path': f's3://{self.silver_bucket_name}/glue-spark-logs/',
                '--bronze_bucket': self.bronze_bucket_name,
                '--silver_bucket': self.silver_bucket_name,
                '--environment': self.environment,
                '--glue_database': self.glue_database_name,
                '--datalake-formats': 'iceberg'
            },
            description='Transforms bronze layer data into normalized silver layer tables'
        )

        return silver_job

    def _create_state_machine(self) -> sfn.StateMachine:
        """
        Create Step Functions state machine for pipeline orchestration.

        Returns:
            State machine
        """
        # Define Lambda invocation task
        invoke_lambda = tasks.LambdaInvoke(
            self, 'InvokeIngestionLambda',
            lambda_function=self.ingestion_lambda,
            payload=sfn.TaskInput.from_object({
                'fiscal_years': sfn.JsonPath.string_at('$.fiscal_years'),
                'include_fields': sfn.JsonPath.string_at('$.include_fields'),
                'additional_criteria': sfn.JsonPath.string_at('$.additional_criteria')
            }),
            result_path='$.lambda_result',
            retry_on_service_exceptions=True
        )

        # Check Lambda status
        check_lambda_success = sfn.Choice(self, 'CheckLambdaSuccess')

        lambda_failed = sfn.Fail(
            self, 'LambdaFailed',
            cause='Lambda ingestion failed',
            error='LambdaError'
        )

        # Define Bronze Glue job task
        run_bronze_job = tasks.GlueStartJobRun(
            self, 'RunBronzeGlueJob',
            glue_job_name=self.bronze_glue_job.name,
            arguments=sfn.TaskInput.from_object({
                '--fiscal_years': sfn.JsonPath.string_at('$.fiscal_years_str')
            }),
            result_path='$.bronze_result',
            integration_pattern=sfn.IntegrationPattern.RUN_JOB
        )

        # Define Silver Glue job task
        run_silver_job = tasks.GlueStartJobRun(
            self, 'RunSilverGlueJob',
            glue_job_name=self.silver_glue_job.name,
            arguments=sfn.TaskInput.from_object({
                '--fiscal_years': sfn.JsonPath.string_at('$.fiscal_years_str')
            }),
            result_path='$.silver_result',
            integration_pattern=sfn.IntegrationPattern.RUN_JOB
        )

        # Success state
        pipeline_succeeded = sfn.Succeed(
            self, 'PipelineSucceeded',
            comment='NIH RePORTER pipeline completed successfully'
        )

        # Build workflow
        definition = invoke_lambda.next(
            check_lambda_success.when(
                sfn.Condition.string_equals('$.lambda_result.Payload.status', 'success'),
                run_bronze_job.next(
                    run_silver_job.next(pipeline_succeeded)
                )
            ).when(
                sfn.Condition.string_equals('$.lambda_result.Payload.status', 'partial_success'),
                run_bronze_job.next(
                    run_silver_job.next(pipeline_succeeded)
                )
            ).otherwise(lambda_failed)
        )

        # Create state machine role
        state_machine_role = iam.Role(
            self, 'NIHReporterStateMachineRole',
            assumed_by=iam.ServicePrincipal('states.amazonaws.com'),
            role_name=f'nih-reporter-state-machine-role-{self.environment}'
        )

        # Grant permissions
        self.ingestion_lambda.grant_invoke(state_machine_role)

        state_machine_role.add_to_policy(iam.PolicyStatement(
            actions=[
                'glue:StartJobRun',
                'glue:GetJobRun',
                'glue:GetJobRuns',
                'glue:BatchStopJobRun'
            ],
            resources=[
                f'arn:aws:glue:{self.region}:{self.account}:job/{self.bronze_glue_job.name}',
                f'arn:aws:glue:{self.region}:{self.account}:job/{self.silver_glue_job.name}'
            ]
        ))

        # Create log group
        log_group = logs.LogGroup(
            self, 'NIHReporterStateMachineLogGroup',
            log_group_name=f'/aws/vendedlogs/states/nih-reporter-{self.environment}',
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_MONTH
        )

        # Create state machine
        state_machine = sfn.StateMachine(
            self, 'NIHReporterStateMachine',
            state_machine_name=f'nih-reporter-pipeline-{self.environment}',
            definition=definition,
            role=state_machine_role,
            logs=sfn.LogOptions(
                destination=log_group,
                level=sfn.LogLevel.ALL
            ),
            tracing_enabled=True
        )

        return state_machine

    def _create_scheduler(self) -> events.Rule:
        """
        Create EventBridge scheduler for periodic pipeline execution.

        Returns:
            EventBridge rule
        """
        # Create rule
        # Weekly on Sundays at 2:00 AM UTC
        rule = events.Rule(
            self, 'NIHReporterScheduleRule',
            rule_name=f'nih-reporter-weekly-schedule-{self.environment}',
            schedule=events.Schedule.cron(
                minute='0',
                hour='2',
                week_day='SUN'
            ),
            description='Triggers NIH RePORTER pipeline weekly on Sundays at 2:00 AM UTC'
        )

        # Add target
        # Default: Process last 2 fiscal years
        import datetime
        current_year = datetime.datetime.now().year
        fiscal_years = [current_year, current_year - 1]

        rule.add_target(
            targets.SfnStateMachine(
                self.state_machine,
                input=events.RuleTargetInput.from_object({
                    'fiscal_years': fiscal_years,
                    'fiscal_years_str': ','.join(map(str, fiscal_years)),
                    'include_fields': None,
                    'additional_criteria': {}
                })
            )
        )

        return rule

    def _create_outputs(self):
        """Create CloudFormation outputs."""
        CfnOutput(
            self, 'LambdaFunctionName',
            value=self.ingestion_lambda.function_name,
            description='NIH RePORTER ingestion Lambda function name'
        )

        CfnOutput(
            self, 'BronzeGlueJobName',
            value=self.bronze_glue_job.name,
            description='NIH RePORTER bronze Glue job name'
        )

        CfnOutput(
            self, 'SilverGlueJobName',
            value=self.silver_glue_job.name,
            description='NIH RePORTER silver Glue job name'
        )

        CfnOutput(
            self, 'StateMachineArn',
            value=self.state_machine.state_machine_arn,
            description='NIH RePORTER pipeline state machine ARN'
        )

        CfnOutput(
            self, 'ScheduleRuleName',
            value=self.scheduler.rule_name,
            description='NIH RePORTER schedule rule name'
        )
