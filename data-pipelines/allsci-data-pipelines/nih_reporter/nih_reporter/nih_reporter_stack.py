from aws_cdk import Stack
from constructs import Construct

from nih_reporter.lambda_function.lambda_app_construct import TriggerLambdaConstruct
from nih_reporter.glue.glue_app_construct import GlueJobConstruct
from nih_reporter.step_functions.step_functions_app_construct import StepFunctionConstruct
from nih_reporter.eventbridge.eventbridge_app_construct import EventBridgeScheduler


class NihReporterStack(Stack):
    """
    NIH Reporter data pipeline stack.
    
    Orchestrates Lambda, Glue, Step Functions, and EventBridge
    for NIH RePORTER API data ingestion and processing.
    """

    def __init__(self, scope: Construct, construct_id: str, environment: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        print(f"Deploying to environment: {environment}")

        # Create Glue jobs
        glue_construct = GlueJobConstruct(
            self, "GlueJobs", environment=environment
        )
        
        # Create Lambda function
        lambda_construct = TriggerLambdaConstruct(
            self, "TriggerLambda", environment=environment
        )
        
        # Create Step Functions workflow
        step_function_construct = StepFunctionConstruct(
            self, "StepFunctionsWorkflow", environment=environment,
            ingestion_lambda_function=lambda_construct.lambda_function,
            bronze_glue_job_name=glue_construct.glue_job_bronze.name,
            silver_glue_job_name=glue_construct.glue_job_silver.name
        )
        
        # Create EventBridge scheduler
        scheduler_construct = EventBridgeScheduler(
            self, "StateMachineScheduler", environment=environment,
            state_machine_arn=step_function_construct.state_machine_arn
        )
