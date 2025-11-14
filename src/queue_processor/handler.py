"""
Task Queue Processor
Processes tasks from SQS FIFO queue with ordering guarantees and retry logic.
"""

import json
import logging
import os
from typing import Any

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Custom exception for task processing errors."""

    pass


def process_task(task_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process a single task with business logic.
    This is idempotent to handle potential duplicate deliveries.

    Args:
        task_data: Task data from queue message

    Returns:
        Processing result dictionary

    Raises:
        ProcessingError: If task processing fails
    """
    task_id = task_data.get("task_id")
    logger.info(f"Processing task {task_id}")

    try:
        # Validate task data structure
        required_fields = ["task_id", "title", "description", "priority", "created_at"]
        for field in required_fields:
            if field not in task_data:
                raise ProcessingError(f"Missing required field: {field}")

        # Simulate processing logic
        # In a real application, this would:
        # - Store task in database
        # - Execute business logic
        # - Trigger downstream processes
        # - Update task status

        logger.info(
            f"Task {task_id} processed successfully: "
            f"{task_data['title']} (priority: {task_data['priority']})"
        )

        # Return processing result
        return {
            "task_id": task_id,
            "status": "completed",
            "message": "Task processed successfully",
        }

    except ProcessingError:
        raise
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        raise ProcessingError(f"Failed to process task: {str(e)}") from e


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for SQS FIFO queue processing.
    Implements partial batch failure reporting for better retry handling.

    Args:
        event: SQS event containing batch of messages
        context: Lambda context

    Returns:
        Batch item failures for partial batch failure handling
    """
    logger.info(f"Processing batch of {len(event.get('Records', []))} messages")

    batch_item_failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")
        receipt_handle = record.get("receiptHandle")

        try:
            logger.debug(
                f"Processing message {message_id} with receipt {receipt_handle}"
            )
            # Parse message body
            body = record.get("body", "{}")
            if isinstance(body, str):
                task_data = json.loads(body)
            else:
                task_data = body

            # Process task (idempotent operation)
            result = process_task(task_data)
            logger.info(f"Message {message_id} processed successfully: {result}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message {message_id}: {str(e)}")
            # Mark as failed for retry
            batch_item_failures.append({"itemIdentifier": message_id})

        except ProcessingError as e:
            logger.error(
                f"Processing error for message {message_id}: {str(e)}",
                exc_info=True,
            )
            # Mark as failed for retry
            batch_item_failures.append({"itemIdentifier": message_id})

        except Exception as e:
            logger.error(
                f"Unexpected error processing message {message_id}: {str(e)}",
                exc_info=True,
            )
            # Mark as failed for retry
            batch_item_failures.append({"itemIdentifier": message_id})

    # Report partial batch failures
    # This allows Lambda to only retry failed messages while keeping successful ones
    if batch_item_failures:
        logger.warning(
            f"Batch processing completed with {len(batch_item_failures)} failures"
        )
    else:
        logger.info("All messages in batch processed successfully")

    return {"batchItemFailures": batch_item_failures}
