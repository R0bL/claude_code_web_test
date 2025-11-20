#!/usr/bin/env python3
"""
NIH RePORTER CDK App

Main entry point for the NIH RePORTER data pipeline CDK application.

Usage:
    cdk deploy --context environment=dev
    cdk deploy --context environment=prod

Author: AllSci Data Pipeline
"""

import os
from aws_cdk import App, Environment, Tags
from nih_reporter.nih_reporter_stack import NIHReporterStack


app = App()

# Get environment from context (default to dev)
environment = app.node.try_get_context('environment') or 'dev'

# Environment-specific configuration
config = {
    'dev': {
        'landing_zone_bucket': 'allsci-landingzone-dev',
        'bronze_bucket': 'allsci-bronze-dev',
        'silver_bucket': 'allsci-silver-dev',
        'glue_database': 'allsci_dev',
        'account': os.environ.get('CDK_DEFAULT_ACCOUNT'),
        'region': os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
    },
    'prod': {
        'landing_zone_bucket': 'allsci-landingzone-prod',
        'bronze_bucket': 'allsci-bronze-prod',
        'silver_bucket': 'allsci-silver-prod',
        'glue_database': 'allsci_prod',
        'account': os.environ.get('CDK_DEFAULT_ACCOUNT'),
        'region': os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
    }
}

# Get configuration for environment
env_config = config.get(environment)

if not env_config:
    raise ValueError(f"Invalid environment: {environment}. Must be 'dev' or 'prod'")

# Create stack
stack = NIHReporterStack(
    app,
    f'NIHReporterStack-{environment}',
    environment=environment,
    landing_zone_bucket_name=env_config['landing_zone_bucket'],
    bronze_bucket_name=env_config['bronze_bucket'],
    silver_bucket_name=env_config['silver_bucket'],
    glue_database_name=env_config['glue_database'],
    env=Environment(
        account=env_config['account'],
        region=env_config['region']
    ),
    description=f'NIH RePORTER data pipeline infrastructure ({environment})'
)

# Add tags
Tags.of(stack).add('Project', 'AllSci')
Tags.of(stack).add('Pipeline', 'NIH_RePORTER')
Tags.of(stack).add('Environment', environment)
Tags.of(stack).add('ManagedBy', 'CDK')

app.synth()
