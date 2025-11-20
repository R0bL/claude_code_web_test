# NIH Reporter Pipeline Refactoring Notes

## Overview

This document outlines the refactoring performed to align the Claude Code-generated NIH Reporter pipeline with AllSci's architectural standards and best practices.

## Critical Issues Addressed

### 1. Monolithic Stack → Modular Constructs

**Before**: Single 494-line `nih_reporter_stack.py` file containing all infrastructure code.

**After**: Separated into focused, reusable constructs:
- `nih_reporter/glue/glue_app_construct.py` - Glue job definitions
- `nih_reporter/lambda_function/lambda_app_construct.py` - Lambda function
- `nih_reporter/step_functions/step_functions_app_construct.py` - Workflow orchestration
- `nih_reporter/eventbridge/eventbridge_app_construct.py` - Scheduling

**Impact**: Improved maintainability, reusability, and testability.

### 2. IAM Role Creation → Shared Role Reference

**Before**: Created new IAM roles in the stack.

**After**: References existing shared role:
```python
self.glue_job_role = iam.Role.from_role_name(
    self, "GlueJobRole",
    role_name=f"allsci-{ENV}-glue-default-service-role"
)
```

**Impact**: Prevents infrastructure bloat and maintains centralized IAM management.

### 3. Minimal Packages → Comprehensive Shared Utilities

**Before**: Only `lake_transformations` package (1 file).

**After**: Complete package structure copied from `nih_clinical_trials_gov`:
- `lake_tools/` - Core transformations, catalogs, upsert queries
- `lake_transformations/` - AllSci ID generation (define_allsci_ids)
- `opensearch/` - OpenSearch connection utilities
- `postgresql/` - PostgreSQL connection utilities
- `utils/` - Athena queries, common functions

**Impact**: Full utility support for production workloads.

### 4. Glue 4.0 → Glue 5.0

**Before**: `glue_version="4.0"`

**After**: `glue_version="5.0"`

**Impact**: Access to latest performance improvements and features.

### 5. No Job Bookmarks → Job Bookmarks Enabled

**Before**: Job bookmarks not configured.

**After**: 
```python
"--job-bookmark-option": "job-bookmark-enable"
```

**Impact**: Prevents reprocessing of data, enables incremental updates.

### 6. Missing VPC Connections → VPC Configured

**Before**: No VPC connections.

**After**:
```python
connections=glue.CfnJob.ConnectionsListProperty(
    connections=[f"allsci-{ENV}-network"]
)
```

**Impact**: Enables access to private resources (RDS, OpenSearch, etc.).

### 7. No Lambda Layers → Lambda Layer Implementation

**Before**: Lambda packages dependencies directly.

**After**: Dependencies packaged in `layer.zip` and attached as layer.

**Impact**: Smaller deployment packages, faster deployments, shared dependencies.

### 8. No Auto-scaling → Auto-scaling Enabled

**Before**: Fixed worker count.

**After**:
```python
"--enable-auto-scaling": "true"
```

**Impact**: Cost optimization through dynamic worker scaling.

### 9. Non-standard Script Locations → Standard AWS Glue Assets

**Before**: Custom S3 paths for scripts.

**After**: Consistent path pattern:
```python
script_location=f"s3://aws-glue-assets-206250664027-us-east-1/cdk/{ENV}/nih_reporter/nih_reporter_bronze.py"
```

**Impact**: Consistent deployment patterns across all pipelines.

### 10. Over-engineered Configuration → Convention-based

**Before**: Explicit parameters in CDK and Glue jobs:
```python
args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'landing_zone_bucket', 'bronze_bucket',
    'environment', 'glue_database', 'fiscal_years'
])
```

**After**: Convention-based naming from ENV:
```python
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'ENV', 'FISCAL_YEARS'])
ENV = args['ENV']
LANDING_ZONE_BUCKET = f"allsci-landingzone-{ENV}"
BRONZE_BUCKET = f"allsci-bronze-{ENV}"
GLUE_DATABASE = f"allsci_{ENV}"
```

**Impact**: Reduced complexity, consistent naming, easier configuration management.

## Additional Improvements

### Directory Structure Reorganization

**Before**:
```
nih_reporter/
├── glue/
│   ├── nih_reporter_bronze.py
│   ├── nih_reporter_silver.py
│   └── package/
│       └── lake_transformations/
├── lambda_function/
│   └── handler.py
└── nih_reporter_stack.py
```

**After**:
```
nih_reporter/
├── glue/
│   ├── glue_app_construct.py
│   ├── jobs/
│   │   ├── nih_reporter_bronze.py
│   │   └── nih_reporter_silver.py
│   └── package/
│       ├── lake_tools/
│       ├── lake_transformations/
│       ├── opensearch/
│       ├── postgresql/
│       └── utils/
├── lambda_function/
│   ├── lambda_app_construct.py
│   ├── scripts/
│   │   └── handler.py
│   ├── layer.zip
│   └── BUILD_LAYER.md
├── step_functions/
│   └── step_functions_app_construct.py
├── eventbridge/
│   └── eventbridge_app_construct.py
└── nih_reporter_stack.py (simplified)
```

### Test Structure

**Before**: Flat test directory.

**After**: Organized test structure:
```
tests/
├── __init__.py
└── unit/
    ├── __init__.py
    ├── test_lambda_handler.py
    └── test_nih_reporter_stack.py
```

### Simplified app.py

**Before**: 100+ lines with explicit configuration dictionaries.

**After**: 20 lines using convention-based configuration:
```python
env_name = app.node.try_get_context("environment")

NihReporterStack(
    app,
    f"NihReporterStack-{env_name}",
    environment=env_name,
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    ),
)
```

## Deployment Differences

### Before
```bash
cdk deploy --context environment=dev \
  --context landing_zone_bucket=... \
  --context bronze_bucket=... \
  --context silver_bucket=... \
  --context glue_database=...
```

### After
```bash
make deploy-dev
# OR
cdk deploy --context environment=dev
```

All bucket names and database names are derived from the environment name.

## Testing

New unit tests added to verify:
- Stack synthesis
- Glue jobs use shared IAM role
- Glue version is 5.0
- Modular constructs are properly instantiated

Run tests:
```bash
make test
```

## Migration Path

If you have an existing deployment of the old architecture:

1. **Backup**: Export data from existing tables
2. **Destroy Old Stack**: `cdk destroy --context environment=dev`
3. **Deploy New Stack**: `make deploy-dev`
4. **Verify**: Check all resources are created correctly
5. **Run Pipeline**: `make trigger-pipeline ENV=dev`
6. **Validate**: Query tables to ensure data is processed correctly

## Documentation Updates

- Updated README with architecture alignment section
- Added BUILD_LAYER.md for Lambda layer instructions
- Added this REFACTORING_NOTES.md document
- Updated Makefile with comprehensive targets

## Key Takeaways

The refactoring transformed a monolithic, over-configured pipeline into a modular, convention-based architecture that:
- Follows AllSci standards
- Reuses shared infrastructure
- Simplifies configuration
- Improves maintainability
- Enables better testing
- Reduces operational complexity

All 10 critical issues have been resolved, bringing the pipeline in line with production standards used across all AllSci data pipelines.

