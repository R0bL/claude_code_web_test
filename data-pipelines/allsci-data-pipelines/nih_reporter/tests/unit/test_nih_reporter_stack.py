import aws_cdk as cdk
import aws_cdk.assertions as assertions
from nih_reporter.nih_reporter_stack import NihReporterStack


def test_nih_reporter_stack_created():
    """Test that the NIH Reporter stack can be synthesized."""
    app = cdk.App()
    
    stack = NihReporterStack(
        app, 
        "TestNihReporterStack",
        environment="dev"
    )
    
    template = assertions.Template.from_stack(stack)
    
    # Verify Glue jobs are created
    template.resource_count_is("AWS::Glue::Job", 2)
    
    # Verify Lambda function is created
    template.resource_count_is("AWS::Lambda::Function", 1)
    
    # Verify Step Functions state machine is created
    template.resource_count_is("AWS::StepFunctions::StateMachine", 1)
    
    # Verify EventBridge rule is created
    template.resource_count_is("AWS::Events::Rule", 1)


def test_glue_jobs_use_shared_role():
    """Test that Glue jobs reference the shared IAM role."""
    app = cdk.App()
    
    stack = NihReporterStack(
        app, 
        "TestNihReporterStack",
        environment="dev"
    )
    
    template = assertions.Template.from_stack(stack)
    
    # Verify Glue jobs use the correct role ARN pattern
    template.has_resource_properties(
        "AWS::Glue::Job",
        {
            "Role": assertions.Match.string_like_regexp(".*allsci-dev-glue-default-service-role.*")
        }
    )


def test_glue_version_is_5():
    """Test that Glue jobs use version 5.0."""
    app = cdk.App()
    
    stack = NihReporterStack(
        app, 
        "TestNihReporterStack",
        environment="dev"
    )
    
    template = assertions.Template.from_stack(stack)
    
    # Verify Glue version
    template.has_resource_properties(
        "AWS::Glue::Job",
        {
            "GlueVersion": "5.0"
        }
    )

