"""
Pytest configuration and shared fixtures.
"""

import os
import sys

import pytest

# Set mock AWS credentials BEFORE any imports
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Disable proxies for boto3
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["NO_PROXY"] = "*"


@pytest.fixture(scope="session", autouse=True)
def aws_credentials():
    """Set up mock AWS credentials for moto."""
    # Already set above, but keep for clarity
    pass


@pytest.fixture(scope="function", autouse=True)
def reset_environment():
    """Reset environment variables between tests."""
    # Store original environment
    original_env = dict(os.environ)
    
    # Set default test environment
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["HTTP_PROXY"] = ""
    os.environ["HTTPS_PROXY"] = ""
    
    yield
    
    # Restore original environment (except AWS credentials)
    os.environ.clear()
    os.environ.update(original_env)
    
    # Ensure AWS credentials remain mocked
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
