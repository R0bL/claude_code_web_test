#!/usr/bin/env python3
import os
import aws_cdk as cdk

from nih_reporter.nih_reporter_stack import NihReporterStack


app = cdk.App()

# Get environment from context
env_name = app.node.try_get_context("environment")

# Create stack with convention-based naming
NihReporterStack(
    app,
    f"NihReporterStack-{env_name}",
    environment=env_name,
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)

app.synth()
