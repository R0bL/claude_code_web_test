from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_iam as iam,
)
from constructs import Construct


class TriggerLambdaConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, environment: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ENV = environment
        ACCOUNT_ID = Stack.of(self).account
        REGION = Stack.of(self).region

        # Create Lambda layer from layer.zip (will be created in Phase 5)
        layer = _lambda.LayerVersion(
            self,
            "LambdaLayer",
            code=_lambda.Code.from_asset("nih_reporter/lambda_function/layer.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
        )

        self.lambda_name = f"{ENV}_allsci_nih_reporter_trigger"
        self.lambda_function = _lambda.Function(
            self,
            "TriggerLambda",
            function_name=self.lambda_name,
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="scripts.handler.lambda_handler",
            code=_lambda.Code.from_asset(
                "nih_reporter/lambda_function",
                exclude=[
                    "__pycache__", "lambda_app_construct.py",
                    "layer.zip", "requirements.txt"
                ]
            ),
            timeout=Duration.minutes(15),
            memory_size=1024,
            reserved_concurrent_executions=5,
            retry_attempts=0,
            layers=[layer],
            environment={
                "TARGET_BUCKET": f"allsci-landingzone-{ENV}",
                "API_BASE_URL": "https://api.reporter.nih.gov",
                "RATE_LIMIT_DELAY": "1.0",
                "MAX_RECORDS_PER_REQUEST": "500",
                "MAX_OFFSET": "14999",
            },
        )

        # S3 permissions
        self.lambda_function.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:ListBucket", "s3:GetObject", "s3:PutObject"],
            resources=[
                f"arn:aws:s3:::allsci-landingzone-{ENV}",
                f"arn:aws:s3:::allsci-landingzone-{ENV}/*",
            ]
        ))

        # EventBridge permissions
        self.lambda_function.add_permission(
            "AllowEventBridgeInvoke",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_account=ACCOUNT_ID,
            source_arn=f"arn:aws:events:{REGION}:{ACCOUNT_ID}:rule/*"
        )

