"""
Unit tests for API Lambda handler
Tests task validation, sanitization, and queue integration.
"""

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
import boto3

# Set environment variables before importing handler
os.environ["TASK_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo"
os.environ["LOG_LEVEL"] = "DEBUG"

# Import after setting env vars
from src.api import handler


@pytest.fixture
def valid_task_data() -> Dict[str, Any]:
    """Fixture providing valid task data."""
    return {
        "title": "Test Task",
        "description": "This is a test task description",
        "priority": "high",
        "due_date": "2025-12-31T23:59:59Z",
    }


@pytest.fixture
def api_gateway_event(valid_task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fixture providing API Gateway event."""
    return {
        "body": json.dumps(valid_task_data),
        "headers": {"Content-Type": "application/json"},
        "httpMethod": "POST",
        "path": "/tasks",
    }


@pytest.fixture
def lambda_context() -> MagicMock:
    """Fixture providing Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 128
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    context.aws_request_id = "test-request-id"
    return context


class TestValidateTask:
    """Tests for task validation function."""
    
    def test_valid_task_with_all_fields(self, valid_task_data: Dict[str, Any]) -> None:
        """Test validation passes for task with all fields."""
        is_valid, error = handler.validate_task(valid_task_data)
        assert is_valid is True
        assert error is None
    
    def test_valid_task_without_due_date(self) -> None:
        """Test validation passes for task without optional due_date."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "medium",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is True
        assert error is None
    
    def test_missing_title(self) -> None:
        """Test validation fails when title is missing."""
        task_data = {
            "description": "Test description",
            "priority": "low",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "title" in error.lower()
    
    def test_missing_description(self) -> None:
        """Test validation fails when description is missing."""
        task_data = {
            "title": "Test Task",
            "priority": "high",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "description" in error.lower()
    
    def test_missing_priority(self) -> None:
        """Test validation fails when priority is missing."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "priority" in error.lower()
    
    def test_empty_title(self) -> None:
        """Test validation fails for empty title."""
        task_data = {
            "title": "   ",
            "description": "Test description",
            "priority": "high",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_title_too_long(self) -> None:
        """Test validation fails for title exceeding 200 characters."""
        task_data = {
            "title": "A" * 201,
            "description": "Test description",
            "priority": "low",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "200" in error
    
    def test_description_too_long(self) -> None:
        """Test validation fails for description exceeding 2000 characters."""
        task_data = {
            "title": "Test Task",
            "description": "A" * 2001,
            "priority": "medium",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "2000" in error
    
    def test_invalid_priority(self) -> None:
        """Test validation fails for invalid priority value."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "urgent",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "priority" in error.lower()
    
    def test_invalid_due_date_format(self) -> None:
        """Test validation fails for invalid due_date format."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "high",
            "due_date": "2025-13-32",  # Invalid date
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "iso 8601" in error.lower()
    
    def test_title_not_string(self) -> None:
        """Test validation fails when title is not a string."""
        task_data = {
            "title": 123,
            "description": "Test description",
            "priority": "low",
        }
        is_valid, error = handler.validate_task(task_data)
        assert is_valid is False
        assert "string" in error.lower()


class TestSanitizeTask:
    """Tests for task sanitization function."""
    
    def test_sanitize_removes_whitespace(self) -> None:
        """Test sanitization removes leading/trailing whitespace."""
        task_data = {
            "title": "  Test Task  ",
            "description": "  Test description  ",
            "priority": "  HIGH  ",
        }
        sanitized = handler.sanitize_task(task_data)
        assert sanitized["title"] == "Test Task"
        assert sanitized["description"] == "Test description"
        assert sanitized["priority"] == "high"
    
    def test_sanitize_lowercase_priority(self) -> None:
        """Test sanitization converts priority to lowercase."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "HIGH",
        }
        sanitized = handler.sanitize_task(task_data)
        assert sanitized["priority"] == "high"
    
    def test_sanitize_with_due_date(self) -> None:
        """Test sanitization preserves due_date when present."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "medium",
            "due_date": "  2025-12-31T23:59:59Z  ",
        }
        sanitized = handler.sanitize_task(task_data)
        assert "due_date" in sanitized
        assert sanitized["due_date"] == "2025-12-31T23:59:59Z"
    
    def test_sanitize_without_due_date(self) -> None:
        """Test sanitization works without due_date."""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "low",
        }
        sanitized = handler.sanitize_task(task_data)
        assert "due_date" not in sanitized


class TestSendToQueue:
    """Tests for sending tasks to SQS queue."""
    
    @mock_aws
    def test_send_to_queue_success(self, valid_task_data: Dict[str, Any]) -> None:
        """Test successfully sending task to queue."""
        # Create queue within the test
        sqs = boto3.client("sqs", region_name="us-east-1")
        response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        os.environ["TASK_QUEUE_URL"] = response["QueueUrl"]
        
        # Reset the SQS client in handler to use mocked one
        handler._sqs_client = None
        
        # Test send to queue
        task_id = handler.send_to_queue(valid_task_data)
        assert task_id is not None
        assert len(task_id) == 36  # UUID length
    
    @mock_aws
    def test_send_to_queue_includes_metadata(
        self, valid_task_data: Dict[str, Any]
    ) -> None:
        """Test message includes task_id and created_at metadata."""
        # Create queue within the test
        sqs = boto3.client("sqs", region_name="us-east-1")
        response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        os.environ["TASK_QUEUE_URL"] = response["QueueUrl"]
        
        # Reset the SQS client in handler to use mocked one
        handler._sqs_client = None
        
        # Send task
        task_id = handler.send_to_queue(valid_task_data)
        
        # Receive message from queue
        messages = sqs.receive_message(
            QueueUrl=os.environ["TASK_QUEUE_URL"], MaxNumberOfMessages=1
        )
        
        assert "Messages" in messages
        message_body = json.loads(messages["Messages"][0]["Body"])
        assert message_body["task_id"] == task_id
        assert "created_at" in message_body
        assert message_body["title"] == valid_task_data["title"]


class TestLambdaHandler:
    """Tests for Lambda handler function."""
    
    @mock_aws
    def test_successful_task_creation(
        self,
        api_gateway_event: Dict[str, Any],
        lambda_context: MagicMock,
    ) -> None:
        """Test successful task creation returns 200."""
        # Create queue within the test
        sqs = boto3.client("sqs", region_name="us-east-1")
        response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        os.environ["TASK_QUEUE_URL"] = response["QueueUrl"]
        
        # Reset the SQS client in handler to use mocked one
        handler._sqs_client = None
        
        # Test handler
        response = handler.lambda_handler(api_gateway_event, lambda_context)
        
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "task_id" in body
        assert body["message"] == "Task created successfully"
        assert body["status"] == "queued"
    
    @mock_aws
    def test_invalid_json_returns_400(self, lambda_context: MagicMock) -> None:
        """Test invalid JSON returns 400 error."""
        event = {
            "body": "invalid json{{{",
        }
        response = handler.lambda_handler(event, lambda_context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    @mock_aws
    def test_missing_required_field_returns_400(
        self, lambda_context: MagicMock
    ) -> None:
        """Test missing required field returns 400 error."""
        event = {
            "body": json.dumps({
                "title": "Test Task",
                # Missing description and priority
            }),
        }
        response = handler.lambda_handler(event, lambda_context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
    
    @mock_aws
    def test_invalid_priority_returns_400(self, lambda_context: MagicMock) -> None:
        """Test invalid priority value returns 400 error."""
        event = {
            "body": json.dumps({
                "title": "Test Task",
                "description": "Test description",
                "priority": "invalid",
            }),
        }
        response = handler.lambda_handler(event, lambda_context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "priority" in body["error"].lower()
    
    @mock_aws
    def test_response_includes_cors_headers(
        self,
        api_gateway_event: Dict[str, Any],
        lambda_context: MagicMock,
    ) -> None:
        """Test response includes proper CORS headers."""
        # Create queue within the test
        sqs = boto3.client("sqs", region_name="us-east-1")
        response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        os.environ["TASK_QUEUE_URL"] = response["QueueUrl"]
        
        # Reset the SQS client in handler to use mocked one
        handler._sqs_client = None
        
        # Test handler
        response = handler.lambda_handler(api_gateway_event, lambda_context)
        
        assert "headers" in response
        assert "Access-Control-Allow-Origin" in response["headers"]
        assert response["headers"]["Content-Type"] == "application/json"


class TestErrorHandling:

    @mock_aws
    def test_send_to_queue_handles_client_error(self) -> None:
        """Test that ClientError in send_to_queue is properly raised."""
        handler._sqs_client = None

        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "priority": "high",
        }

        # Mock the SQS client to raise ClientError
        with patch.object(handler, '_get_sqs_client') as mock_get_client:
            mock_sqs = MagicMock()
            mock_sqs.send_message.side_effect = ClientError(
                {'Error': {'Code': 'NonExistentQueue', 'Message': 'Queue does not exist'}},
                'SendMessage'
            )
            mock_get_client.return_value = mock_sqs

            with pytest.raises(ClientError):
                handler.send_to_queue(task_data)
    
    @mock_aws  
    def test_lambda_handler_handles_sqs_client_error(self) -> None:
        """Test lambda_handler returns 500 when SQS fails."""
        # Don't create a queue - this will cause send_to_queue to fail
        os.environ["TASK_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789012/nonexistent-queue.fifo"
        handler._sqs_client = None
        
        context = MagicMock()
        event = {
            "body": json.dumps({
                "title": "Test Task",
                "description": "Test description",
                "priority": "high",
            }),
        }
        
        response = handler.lambda_handler(event, context)
        
        # Should return 500 error
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        assert "Failed to process task" in body["error"]
    
    @mock_aws
    def test_lambda_handler_handles_unexpected_exception(self) -> None:
        """Test lambda_handler handles unexpected exceptions."""
        context = MagicMock()
        
        # Patch validate_task to raise an unexpected exception
        with patch.object(handler, 'validate_task', side_effect=RuntimeError("Unexpected error")):
            event = {
                "body": json.dumps({
                    "title": "Test Task",
                    "description": "Test description",
                    "priority": "high",
                }),
            }
            
            response = handler.lambda_handler(event, context)
            
            # Should return 500 error
            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert "error" in body
            assert "Internal server error" in body["error"]
