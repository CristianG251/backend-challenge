.PHONY: help install test coverage lint format type-check clean cdk-synth cdk-deploy cdk-destroy

help:
	@echo "Task Management API - Available Commands"
	@echo "========================================"
	@echo "install        - Install all dependencies"
	@echo "test           - Run all tests"
	@echo "test-unit      - Run unit tests only"
	@echo "test-integration - Run integration tests only"
	@echo "coverage       - Run tests with coverage report"
	@echo "lint           - Run code linting"
	@echo "format         - Format code with Black"
	@echo "type-check     - Run type checking with pyright"
	@echo "clean          - Remove build artifacts"
	@echo "cdk-synth      - Synthesize CloudFormation templates"
	@echo "cdk-deploy     - Deploy to AWS"
	@echo "cdk-destroy    - Destroy AWS resources"
	@echo "validate       - Run all quality checks"

install:
	@echo "Installing Python dependencies..."
	pip install -r requirements-dev.txt
	@echo "Installing CDK dependencies..."
	cd infrastructure && npm install

test:
	@echo "Running all tests..."
	pytest -v

test-unit:
	@echo "Running unit tests..."
	pytest -m unit -v

test-integration:
	@echo "Running integration tests..."
	pytest -m integration -v

coverage:
	@echo "Running tests with coverage..."
	pytest --cov=src --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	@echo "Running linting..."
	ruff check src tests

format:
	@echo "Formatting code..."
	black src tests
	@echo "Code formatted successfully"

type-check:
	@echo "Running type checking..."
	pyright src tests

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov .coverage coverage.xml
	rm -rf infrastructure/cdk.out infrastructure/dist infrastructure/node_modules
	@echo "Clean complete"

cdk-synth:
	@echo "Synthesizing CDK stacks..."
	cd infrastructure && npm run build && npx cdk synth

cdk-deploy:
	@echo "Deploying to AWS..."
	cd infrastructure && npx cdk deploy --all

cdk-destroy:
	@echo "Destroying AWS resources..."
	cd infrastructure && npx cdk destroy --all

validate:
	@echo "Running all quality checks..."
	@make format
	@make lint
	@make type-check
	@make coverage
	@echo "✅ All quality checks passed!"
