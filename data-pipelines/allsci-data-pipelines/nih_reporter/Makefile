.PHONY: help install install-dev clean test lint format deploy destroy synth diff bootstrap upload-scripts

# Default environment
ENV ?= dev

help: ## Show this help message
	@echo 'Usage: make [target] ENV=<dev|prod>'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements-dev.txt

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf cdk.out/
	rm -rf .coverage
	rm -rf htmlcov/

test: ## Run unit tests
	pytest tests/ -v --cov=nih_reporter --cov-report=term-missing

lint: ## Run linting checks
	flake8 nih_reporter/ tests/
	mypy nih_reporter/
	pylint nih_reporter/

format: ## Format code with black
	black nih_reporter/ tests/ app.py

synth: ## Synthesize CDK stack
	cdk synth --context environment=$(ENV)

diff: ## Show CDK diff
	cdk diff --context environment=$(ENV)

bootstrap: ## Bootstrap CDK environment
	cdk bootstrap --context environment=$(ENV)

upload-scripts: ## Upload Glue scripts to S3
	@echo "Uploading Glue scripts to S3..."
	aws s3 cp nih_reporter/glue/nih_reporter_bronze.py s3://allsci-bronze-$(ENV)/glue-scripts/
	aws s3 cp nih_reporter/glue/nih_reporter_silver.py s3://allsci-silver-$(ENV)/glue-scripts/
	@echo "Scripts uploaded successfully"

deploy: upload-scripts ## Deploy CDK stack
	cdk deploy --context environment=$(ENV) --require-approval never

destroy: ## Destroy CDK stack
	cdk destroy --context environment=$(ENV) --force

# Manual job triggers
trigger-lambda: ## Manually trigger Lambda function
	@echo "Triggering Lambda function..."
	aws lambda invoke \
		--function-name nih-reporter-ingestion-$(ENV) \
		--payload '{"fiscal_years": [2024, 2023]}' \
		--cli-binary-format raw-in-base64-out \
		response.json
	@cat response.json
	@rm response.json

trigger-bronze: ## Manually trigger Bronze Glue job
	@echo "Triggering Bronze Glue job..."
	aws glue start-job-run \
		--job-name nih-reporter-bronze-$(ENV) \
		--arguments '{"--fiscal_years": "2024,2023"}'

trigger-silver: ## Manually trigger Silver Glue job
	@echo "Triggering Silver Glue job..."
	aws glue start-job-run \
		--job-name nih-reporter-silver-$(ENV) \
		--arguments '{"--fiscal_years": "2024,2023"}'

trigger-pipeline: ## Manually trigger Step Functions pipeline
	@echo "Triggering Step Functions pipeline..."
	aws stepfunctions start-execution \
		--state-machine-arn $$(aws stepfunctions list-state-machines --query "stateMachines[?name=='nih-reporter-pipeline-$(ENV)'].stateMachineArn" --output text) \
		--input '{"fiscal_years": [2024, 2023], "fiscal_years_str": "2024,2023"}'

# Query examples
query-bronze: ## Query bronze table
	@echo "SELECT COUNT(*) FROM nih_reporter_projects_bronze WHERE fiscal_year IN (2024, 2023);" | \
		aws athena start-query-execution \
		--query-string "SELECT COUNT(*) FROM allsci_$(ENV).nih_reporter_projects_bronze WHERE fiscal_year IN (2024, 2023);" \
		--result-configuration "OutputLocation=s3://allsci-bronze-$(ENV)/athena-results/"

query-silver-projects: ## Query silver projects table
	@echo "SELECT COUNT(*) FROM dim_nih_projects WHERE fiscal_year = 2024;" | \
		aws athena start-query-execution \
		--query-string "SELECT COUNT(*) FROM allsci_$(ENV).dim_nih_projects WHERE fiscal_year = 2024;" \
		--result-configuration "OutputLocation=s3://allsci-silver-$(ENV)/athena-results/"
