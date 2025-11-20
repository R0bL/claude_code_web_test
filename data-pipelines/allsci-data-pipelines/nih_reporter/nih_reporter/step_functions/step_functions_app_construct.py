from aws_cdk import (
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_logs as logs,
    RemovalPolicy
)
from constructs import Construct


class StepFunctionConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        ingestion_lambda_function,
        bronze_glue_job_name: str,
        silver_glue_job_name: str,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        ENV = environment

        # Define workflow tasks
        invoke_lambda = tasks.LambdaInvoke(
            self, 'InvokeIngestionLambda',
            lambda_function=ingestion_lambda_function,
            payload=sfn.TaskInput.from_object({
                'fiscal_years': sfn.JsonPath.string_at('$.fiscal_years'),
            }),
            result_path='$.lambda_result'
        )

        run_bronze = tasks.GlueStartJobRun(
            self, 'RunBronzeJob',
            glue_job_name=bronze_glue_job_name,
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            arguments=sfn.TaskInput.from_object({
                '--FISCAL_YEARS': sfn.JsonPath.string_at('$.fiscal_years_str'),
            }),
            result_path='$.bronze_result'
        )

        run_silver = tasks.GlueStartJobRun(
            self, 'RunSilverJob',
            glue_job_name=silver_glue_job_name,
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            arguments=sfn.TaskInput.from_object({
                '--FISCAL_YEARS': sfn.JsonPath.string_at('$.fiscal_years_str'),
            }),
            result_path='$.silver_result'
        )

        success = sfn.Succeed(self, 'Success')

        # Build workflow: Lambda -> Bronze -> Silver -> Success
        definition = invoke_lambda.next(run_bronze).next(run_silver).next(success)

        # Create log group
        log_group = logs.LogGroup(
            self, 'LogGroup',
            log_group_name=f'/aws/vendedlogs/states/nih-reporter-{ENV}',
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_MONTH
        )

        # Create state machine
        self.state_machine = sfn.StateMachine(
            self,
            'NIHReporterStateMachine',
            state_machine_name=f'nih-reporter-pipeline-{ENV}',
            definition=definition,
            logs=sfn.LogOptions(
                destination=log_group,
                level=sfn.LogLevel.ALL
            ),
            tracing_enabled=True
        )

        self.state_machine_arn = self.state_machine.state_machine_arn

