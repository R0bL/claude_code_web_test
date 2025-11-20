.PHONY: help install synth deploy-dev deploy-prod destroy-dev destroy-prod test clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make synth        - Synthesize CDK stack"
	@echo "  make deploy-dev   - Deploy to dev environment"
	@echo "  make deploy-prod  - Deploy to prod environment"
	@echo "  make destroy-dev  - Destroy dev environment"
	@echo "  make destroy-prod - Destroy prod environment"
	@echo "  make test         - Run unit tests"
	@echo "  make clean        - Clean build artifacts"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

synth:
	cdk synth --context environment=dev

deploy-dev:
	cdk deploy --context environment=dev

deploy-prod:
	@echo "WARNING: Deploying to production"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cdk deploy --context environment=prod; \
	fi

destroy-dev:
	cdk destroy --context environment=dev

destroy-prod:
	@echo "WARNING: Destroying production resources"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cdk destroy --context environment=prod; \
	fi

test:
	pytest tests/

clean:
	rm -rf cdk.out
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
