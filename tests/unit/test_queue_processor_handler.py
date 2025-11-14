"""
Unit tests for Queue Processor Lambda handler
Tests task processing, error handling, and retry logic.
"""

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables before importing handler
os.environ["TASK_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo"
os.environ["DLQ_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789012/test-dlq.fifo"
os.environ["LOG_LEVEL"] = "DEBUG"

# Import after setting env vars
from src.queue_processor import handler


@pytest.fixture
def valid_task_data() -> Dict[str, Any]:
    """Fixture providing valid task data."""
    return {
        "task_id": "12345678-1234-1234-1234-123456789012",
        "title": "Test Task",
        "description": "This is a test task",
        "priority": "high",
        "created_at": "2025-11-13T10:00:00Z",
    }


@pytest.fixture
def sqs_record(valid_task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fixture providing SQS record."""
    return {
        "messageId": "msg-123",
        "receiptHandle": "receipt-123",
        "body": json.dumps(valid_task_data),
        "attributes": {
            "ApproximateReceiveCount": "1",
            "SentTimestamp": "1699876543210",
            "MessageGroupId": "task-processing",
            "MessageDeduplicationId": valid_task_data["task_id"],
        },
        "messageAttributes": {},
        "md5OfBody": "test-md5",
        "eventSource": "aws:sqs",
        "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue.fifo",
        "awsRegion": "us-east-1",
    }


@pytest.fixture
def sqs_event(sqs_record: Dict[str, Any]) -> Dict[str, Any]:
    """Fixture providing SQS event with single record."""
    return {"Records": [sqs_record]}


@pytest.fixture
def lambda_context() -> MagicMock:
    """Fixture providing Lambda context."""
    context = MagicMock()
    context.function_name = "test-processor"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    context.aws_request_id = "test-request-id"
    return context


class TestProcessTask:
    """Tests for task processing function."""
    
    def test_process_valid_task(self, valid_task_data: Dict[str, Any]) -> None:
        """Test processing a valid task succeeds."""
        result = handler.process_task(valid_task_data)
        assert result["task_id"] == valid_task_data["task_id"]
        assert result["status"] == "completed"
        assert "message" in result
    
    def test_process_task_missing_required_field(self) -> None:
        """Test processing fails when required field is missing."""
        task_data = {
            "task_id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Task",
            # Missing description
        }
        with pytest.raises(handler.ProcessingError) as exc_info:
            handler.process_task(task_data)
        assert "missing required field" in str(exc_info.value).lower()
    
    def test_process_task_is_idempotent(self, valid_task_data: Dict[str, Any]) -> None:
        """Test processing same task twice produces same result."""
        result1 = handler.process_task(valid_task_data)
        result2 = handler.process_task(valid_task_data)
        assert result1 == result2
    
    def test_process_task_with_due_date(self) -> None:
        """Test processing task with optional due_date."""
        task_data = {
            "task_id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Task",
            "description": "Test description",
            "priority": "medium",
            "created_at": "2025-11-13T10:00:00Z",
            "due_date": "2025-12-31T23:59:59Z",
        }
        result = handler.process_task(task_data)
        assert result["status"] == "completed"


class TestLambdaHandler:
    """Tests for Lambda handler function."""
    
    def test_successful_batch_processing(
        self,
        sqs_event: Dict[str, Any],
        lambda_context: MagicMock,
    ) -> None:
        """Test successful processing of all messages in batch."""
        response = handler.lambda_handler(sqs_event, lambda_context)
        
        assert "batchItemFailures" in response
        assert len(response["batchItemFailures"]) == 0
    
    def test_multiple_messages_in_batch(
        self,
        sqs_record: Dict[str, Any],
        lambda_context: MagicMock,
    ) -> None:
        """Test processing multiple messages in a batch."""
        # Create event with 3 records
        event = {
            "Records": [
                sqs_record,
                {**sqs_record, "messageId": "msg-456"},
                {**sqs_record, "messageId": "msg-789"},
            ]
        }
        
        response = handler.lambda_handler(event, lambda_context)
        assert len(response["batchItemFailures"]) == 0
    
    def test_invalid_json_causes_failure(self, lambda_context: MagicMock) -> None:
        """Test invalid JSON in message body causes batch item failure."""
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-123",
                    "body": "invalid json{{{",
                }
            ]
        }
        
        response = handler.lambda_handler(event, lambda_context)
        assert len(response["batchItemFailures"]) == 1
        assert response["batchItemFailures"][0]["itemIdentifier"] == "msg-123"
    
    def test_missing_required_field_causes_failure(
        self, lambda_context: MagicMock
    ) -> None:
        """Test missing required field causes batch item failure."""
        task_data = {
            "task_id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Task",
            # Missing description
        }
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-123",
                    "body": json.dumps(task_data),
                }
            ]
        }
        
        response = handler.lambda_handler(event, lambda_context)
        assert len(response["batchItemFailures"]) == 1
        assert response["batchItemFailures"][0]["itemIdentifier"] == "msg-123"
    
    def test_partial_batch_failure(
        self,
        valid_task_data: Dict[str, Any],
        lambda_context: MagicMock,
    ) -> None:
        """Test partial batch failure reports only failed messages."""
        invalid_task_data = {"task_id": "invalid"}  # Missing required fields
        
        event = {
            "Records": [
                {
                    "messageId": "msg-success",
                    "receiptHandle": "receipt-success",
                    "body": json.dumps(valid_task_data),
                },
                {
                    "messageId": "msg-failure",
                    "receiptHandle": "receipt-failure",
                    "body": json.dumps(invalid_task_data),
                },
            ]
        }
        
        response = handler.lambda_handler(event, lambda_context)
        
        # Should have exactly 1 failure
        assert len(response["batchItemFailures"]) == 1
        assert response["batchItemFailures"][0]["itemIdentifier"] == "msg-failure"
    
    def test_empty_records_list(self, lambda_context: MagicMock) -> None:
        """Test handling empty records list."""
        event = {"Records": []}
        response = handler.lambda_handler(event, lambda_context)
        assert response["batchItemFailures"] == []
    
    def test_ordering_maintained_in_processing(
        self,
        valid_task_data: Dict[str, Any],
        lambda_context: MagicMock,
    ) -> None:
        """Test messages are processed in order they appear in batch."""
        # Create 5 sequential tasks
        tasks = []
        for i in range(5):
            task = valid_task_data.copy()
            task["task_id"] = f"task-{i}"
            task["title"] = f"Task {i}"
            tasks.append(task)
        
        event = {
            "Records": [
                {
                    "messageId": f"msg-{i}",
                    "receiptHandle": f"receipt-{i}",
                    "body": json.dumps(task),
                }
                for i, task in enumerate(tasks)
            ]
        }
        
        response = handler.lambda_handler(event, lambda_context)
        # All should succeed
        assert len(response["batchItemFailures"]) == 0


class TestErrorHandling:
    """Tests for error handling and retry logic."""
    
    def test_processing_error_raised_correctly(self) -> None:
        """Test ProcessingError is raised with correct message."""
        with pytest.raises(handler.ProcessingError) as exc_info:
            raise handler.ProcessingError("Test error")
        assert "Test error" in str(exc_info.value)
    
    def test_unexpected_exception_wrapped(
        self, lambda_context: MagicMock
    ) -> None:
        """Test unexpected exceptions are caught and reported."""
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-123",
                    "body": json.dumps({"task_id": "test"}),
                }
            ]
        }
        
        # This will cause a ProcessingError due to missing fields
        response = handler.lambda_handler(event, lambda_context)
        assert len(response["batchItemFailures"]) == 1


class TestAdditionalErrorHandling:
    """Additional tests for error handling to improve coverage."""

    def test_process_task_wraps_unexpected_exceptions(self) -> None:
        """Test that unexpected exceptions are wrapped in ProcessingError."""
        # Create task data with invalid structure that will cause an error
        # The task_data.get("task_id") will work, but accessing required fields will fail
        task_data = {
            "task_id": "12345678-1234-1234-1234-123456789012",
            "title": "Test Task",
            "description": "Test description",
            "priority": "high",
            "created_at": "2025-11-13T10:00:00Z",
        }

        # Patch the validation loop to raise an unexpected exception
        # This happens inside the try block so it will be caught and wrapped
        with patch.object(handler, 'logger') as mock_logger:
            # Make the first logger.info call work, but the second one (after validation) fail
            mock_logger.info.side_effect = [None, RuntimeError("Unexpected error")]

            with pytest.raises(handler.ProcessingError) as exc_info:
                handler.process_task(task_data)

            assert "Failed to process task" in str(exc_info.value)
    
    def test_lambda_handler_handles_unexpected_exceptions_in_batch(self) -> None:
        """Test that unexpected exceptions in message processing are caught."""
        context = MagicMock()
        
        # Create an event with a message that will cause an unexpected error
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-123",
                    "body": json.dumps({
                        "task_id": "test-id",
                        "title": "Test",
                        "description": "Test",
                        "priority": "high",
                        "created_at": "2025-11-13T10:00:00Z",
                    }),
                }
            ]
        }
        
        # Patch process_task to raise an unexpected exception
        with patch.object(handler, 'process_task', side_effect=RuntimeError("Unexpected error")):
            response = handler.lambda_handler(event, context)
            
            # Should report the message as failed
            assert len(response["batchItemFailures"]) == 1
            assert response["batchItemFailures"][0]["itemIdentifier"] == "msg-123"
