"""
Integration tests for task management system.
Tests end-to-end flow from API to queue processing.
"""

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

# Set environment variables
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def lambda_context() -> MagicMock:
    """Fixture providing Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
    context.aws_request_id = "test-request-id"
    return context


@pytest.mark.integration
class TestEndToEndFlow:
    """Integration tests for complete task flow."""
    
    @mock_aws
    def test_task_creation_and_processing(
        self, lambda_context: MagicMock
    ) -> None:
        """Test complete flow from API to queue processing."""
        # Set up SQS queues
        sqs = boto3.client("sqs", region_name="us-east-1")
        
        # Create FIFO queue
        queue_response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
                "VisibilityTimeout": "300",
            },
        )
        
        # Create DLQ
        dlq_response = sqs.create_queue(
            QueueName="test-dlq.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        
        queue_url = queue_response["QueueUrl"]
        dlq_url = dlq_response["QueueUrl"]
        
        # Import handlers after setting up environment
        os.environ["TASK_QUEUE_URL"] = queue_url
        os.environ["DLQ_URL"] = dlq_url
        
        # Reset handlers' AWS clients to use mocked ones
        from src.api import handler as api_handler
        from src.queue_processor import handler as processor_handler
        api_handler._sqs_client = None
        
        # Step 1: Create task via API
        api_event = {
            "body": json.dumps({
                "title": "Integration Test Task",
                "description": "This is an integration test",
                "priority": "high",
                "due_date": "2025-12-31T23:59:59Z",
            }),
            "headers": {"Content-Type": "application/json"},
            "httpMethod": "POST",
            "path": "/tasks",
        }
        
        api_response = api_handler.lambda_handler(api_event, lambda_context)
        
        # Verify API response
        assert api_response["statusCode"] == 200
        api_body = json.loads(api_response["body"])
        assert "task_id" in api_body
        task_id = api_body["task_id"]
        
        # Step 2: Verify message in queue
        messages = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1,
        )
        
        assert "Messages" in messages
        assert len(messages["Messages"]) == 1
        
        # Step 3: Process message
        sqs_event = {
            "Records": [
                {
                    "messageId": messages["Messages"][0]["MessageId"],
                    "receiptHandle": messages["Messages"][0]["ReceiptHandle"],
                    "body": messages["Messages"][0]["Body"],
                    "attributes": {},
                    "messageAttributes": {},
                    "md5OfBody": messages["Messages"][0]["MD5OfBody"],
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue.fifo",
                    "awsRegion": "us-east-1",
                }
            ]
        }
        
        processor_response = processor_handler.lambda_handler(
            sqs_event, lambda_context
        )
        
        # Verify processing succeeded
        assert processor_response["batchItemFailures"] == []
        
        # Verify message processed correctly
        message_body = json.loads(messages["Messages"][0]["Body"])
        assert message_body["task_id"] == task_id
        assert message_body["title"] == "Integration Test Task"
    
    @mock_aws
    def test_ordering_preserved_across_multiple_tasks(
        self, lambda_context: MagicMock
    ) -> None:
        """Test that task ordering is preserved through the system."""
        # Set up SQS queues
        sqs = boto3.client("sqs", region_name="us-east-1")
        
        queue_response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
                "VisibilityTimeout": "300",
            },
        )
        
        dlq_response = sqs.create_queue(
            QueueName="test-dlq.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        
        queue_url = queue_response["QueueUrl"]
        dlq_url = dlq_response["QueueUrl"]
        
        os.environ["TASK_QUEUE_URL"] = queue_url
        os.environ["DLQ_URL"] = dlq_url
        
        from src.api import handler as api_handler
        from src.queue_processor import handler as processor_handler
        api_handler._sqs_client = None
        
        # Create multiple tasks in sequence
        task_ids = []
        for i in range(5):
            api_event = {
                "body": json.dumps({
                    "title": f"Task {i}",
                    "description": f"Description for task {i}",
                    "priority": "medium",
                }),
            }
            
            response = api_handler.lambda_handler(api_event, lambda_context)
            body = json.loads(response["body"])
            task_ids.append(body["task_id"])
        
        # Receive and verify messages are in order
        received_tasks = []
        for _ in range(5):
            messages = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )
            
            if "Messages" in messages:
                body = json.loads(messages["Messages"][0]["Body"])
                received_tasks.append(body["task_id"])
                
                # Delete message to get next one
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=messages["Messages"][0]["ReceiptHandle"],
                )
        
        # Verify order maintained
        assert received_tasks == task_ids
    
    @mock_aws
    def test_invalid_task_not_queued(
        self, lambda_context: MagicMock
    ) -> None:
        """Test that invalid tasks are rejected and not queued."""
        # Set up SQS queue
        sqs = boto3.client("sqs", region_name="us-east-1")
        
        queue_response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        
        queue_url = queue_response["QueueUrl"]
        os.environ["TASK_QUEUE_URL"] = queue_url
        
        from src.api import handler as api_handler
        api_handler._sqs_client = None
        
        # Attempt to create invalid task
        api_event = {
            "body": json.dumps({
                "title": "Test Task",
                # Missing required fields
            }),
        }
        
        api_response = api_handler.lambda_handler(api_event, lambda_context)
        
        # Verify API rejected request
        assert api_response["statusCode"] == 400
        
        # Verify no message in queue
        messages = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1,
        )
        
        assert "Messages" not in messages
    
    @mock_aws
    def test_task_with_all_priorities(
        self, lambda_context: MagicMock
    ) -> None:
        """Test tasks with all priority levels."""
        # Set up SQS queues
        sqs = boto3.client("sqs", region_name="us-east-1")
        
        queue_response = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
                "VisibilityTimeout": "300",
            },
        )
        
        dlq_response = sqs.create_queue(
            QueueName="test-dlq.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        
        queue_url = queue_response["QueueUrl"]
        dlq_url = dlq_response["QueueUrl"]
        
        os.environ["TASK_QUEUE_URL"] = queue_url
        os.environ["DLQ_URL"] = dlq_url
        
        from src.api import handler as api_handler
        from src.queue_processor import handler as processor_handler
        api_handler._sqs_client = None
        
        priorities = ["low", "medium", "high"]
        
        for priority in priorities:
            # Create task
            api_event = {
                "body": json.dumps({
                    "title": f"{priority.capitalize()} Priority Task",
                    "description": f"Task with {priority} priority",
                    "priority": priority,
                }),
            }
            
            api_response = api_handler.lambda_handler(api_event, lambda_context)
            assert api_response["statusCode"] == 200
            
            # Receive message
            messages = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,  # Wait a bit longer for message
            )
            
            # Verify message exists
            assert "Messages" in messages, f"No message found for priority {priority}"
            assert len(messages["Messages"]) == 1
            
            # Process message
            sqs_event = {
                "Records": [
                    {
                        "messageId": messages["Messages"][0]["MessageId"],
                        "receiptHandle": messages["Messages"][0]["ReceiptHandle"],
                        "body": messages["Messages"][0]["Body"],
                        "attributes": {},
                        "messageAttributes": {},
                        "md5OfBody": messages["Messages"][0].get("MD5OfBody", ""),
                        "eventSource": "aws:sqs",
                        "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue.fifo",
                        "awsRegion": "us-east-1",
                    }
                ]
            }
            
            processor_response = processor_handler.lambda_handler(
                sqs_event, lambda_context
            )
            assert processor_response["batchItemFailures"] == []
            
            # Delete message after processing
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=messages["Messages"][0]["ReceiptHandle"],
            )
