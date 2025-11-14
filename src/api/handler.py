"""
Task Management API Handler
Handles POST /tasks endpoint with comprehensive validation and SQS integration.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Environment variables
TASK_QUEUE_URL = os.environ.get("TASK_QUEUE_URL", "")

# AWS client will be initialized when needed
_sqs_client = None


def get_sqs_client():
    """Get or create SQS client (lazy initialization)."""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def validate_task(task_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate task data according to requirements.

    Args:
        task_data: Dictionary containing task information

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    if "title" not in task_data:
        return False, "Missing required field: title"
    if "description" not in task_data:
        return False, "Missing required field: description"
    if "priority" not in task_data:
        return False, "Missing required field: priority"

    # Validate title
    title = task_data.get("title", "")
    if not isinstance(title, str):
        return False, "title must be a string"
    if not title.strip():
        return False, "title cannot be empty"
    if len(title) > 200:
        return False, "title cannot exceed 200 characters"

    # Validate description
    description = task_data.get("description", "")
    if not isinstance(description, str):
        return False, "description must be a string"
    if not description.strip():
        return False, "description cannot be empty"
    if len(description) > 2000:
        return False, "description cannot exceed 2000 characters"

    # Validate priority
    priority = task_data.get("priority", "")
    valid_priorities = ["low", "medium", "high"]
    if priority not in valid_priorities:
        return False, f"priority must be one of: {', '.join(valid_priorities)}"

    # Validate due_date if provided
    due_date = task_data.get("due_date")
    if due_date is not None:
        if not isinstance(due_date, str):
            return False, "due_date must be a string in ISO 8601 format"
        try:
            # Validate ISO 8601 format
            datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False, "due_date must be in ISO 8601 format"

    return True, None


def sanitize_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize task data by removing potentially harmful content.

    Args:
        task_data: Dictionary containing task information

    Returns:
        Sanitized task data
    """
    sanitized = {
        "title": task_data["title"].strip(),
        "description": task_data["description"].strip(),
        "priority": task_data["priority"].strip().lower(),
    }

    if "due_date" in task_data and task_data["due_date"]:
        sanitized["due_date"] = task_data["due_date"].strip()

    return sanitized


def send_to_queue(task_data: Dict[str, Any]) -> str:
    """
    Send validated task to SQS FIFO queue with ordering guarantees.

    Args:
        task_data: Validated and sanitized task data

    Returns:
        Task ID (message ID from SQS)

    Raises:
        ClientError: If SQS operation fails
    """
    task_id = str(uuid.uuid4())

    # Add metadata
    message_body = {
        "task_id": task_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **task_data,
    }

    try:
        # Send to FIFO queue with message group ID for ordering
        # Using a single message group ID ensures strict FIFO ordering
        sqs = get_sqs_client()
        response = sqs.send_message(
            QueueUrl=TASK_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageGroupId="task-processing",  # Single group for strict ordering
            MessageDeduplicationId=task_id,  # Prevent duplicates
        )

        logger.info(f"Task {task_id} sent to queue successfully")
        return task_id

    except ClientError as e:
        logger.error(f"Failed to send task to queue: {str(e)}")
        raise


def create_response(
    status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create API Gateway response with proper headers.

    Args:
        status_code: HTTP status code
        body: Response body
        headers: Additional headers

    Returns:
        API Gateway response dictionary
    """
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for task creation endpoint.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                task_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {"error": "Invalid JSON in request body"})
        else:
            task_data = body

        # Validate task data
        is_valid, error_message = validate_task(task_data)
        if not is_valid:
            logger.warning(f"Validation failed: {error_message}")
            return create_response(400, {"error": error_message})

        # Sanitize task data
        sanitized_task = sanitize_task(task_data)

        # Send to queue
        task_id = send_to_queue(sanitized_task)

        # Return success response
        return create_response(
            200,
            {
                "task_id": task_id,
                "message": "Task created successfully",
                "status": "queued",
            },
        )

    except ClientError as e:
        logger.error(f"AWS service error: {str(e)}")
        return create_response(
            500, {"error": "Failed to process task", "details": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return create_response(
            500, {"error": "Internal server error", "details": str(e)}
        )
