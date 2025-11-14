# Architecture Documentation

## System Overview

The Task Management API is a serverless, event-driven system built on AWS that provides reliable, ordered task processing with comprehensive error handling and monitoring.

## Core Components

### 1. API Gateway + Lambda (API Stack)

**Purpose**: Accept and validate incoming task creation requests.

**Components**:
- **API Gateway**: REST API endpoint exposing POST /tasks
- **API Lambda**: Python 3.12 function handling requests

**Flow**:
1. Client sends POST request to /tasks
2. API Gateway invokes Lambda with request payload
3. Lambda validates and sanitizes input
4. Lambda sends message to SQS FIFO queue
5. Returns task_id and success status to client

**Key Features**:
- Comprehensive input validation (title, description, priority, due_date)
- Input sanitization to prevent injection attacks
- CORS support for web clients
- Proper error handling with appropriate HTTP status codes

### 2. SQS FIFO Queue (Queue Stack)

**Purpose**: Provide ordered, reliable message queue for task processing.

**Configuration**:
- **Queue Type**: FIFO (First-In-First-Out)
- **Message Group ID**: Single group "task-processing" for strict ordering
- **Content-Based Deduplication**: Enabled to prevent duplicates
- **Visibility Timeout**: 300 seconds (5 minutes)
- **Retention Period**: 4 days
- **DLQ Max Receive Count**: 3 attempts

**Ordering Guarantees**:
```
Message Group ID: task-processing (single group)
├── Task 1 (Created: T0)
├── Task 2 (Created: T1)
├── Task 3 (Created: T2)
└── Task 4 (Created: T3)

Processing Order: 1 → 2 → 3 → 4 (guaranteed)
```

### 3. Processor Lambda (Queue Stack)

**Purpose**: Process tasks from queue with retry logic.

**Configuration**:
- **Runtime**: Python 3.12
- **Timeout**: 60 seconds
- **Memory**: 512 MB
- **Reserved Concurrency**: 10
- **Event Source**: SQS with batch size 10

**Processing Logic**:
1. Receive batch of up to 10 messages
2. Process each message sequentially
3. Report partial batch failures for retry
4. Failed messages (after 3 attempts) go to DLQ

**Idempotency**:
- Processing logic is idempotent
- Safe to process same message multiple times
- Uses MessageDeduplicationId to track

### 4. Dead Letter Queue (Queue Stack)

**Purpose**: Capture failed messages for investigation.

**Configuration**:
- **Queue Type**: FIFO
- **Retention Period**: 14 days
- **Alarm**: Triggers when messages present

### 5. Monitoring (Monitoring Stack)

**Purpose**: Provide observability and alerting.

**Components**:
- **CloudWatch Dashboard**: Real-time metrics visualization
- **Alarms**: 
  - API Lambda errors (>5 in 5 minutes)
  - Processor Lambda errors (>10 in 5 minutes)
  - DLQ messages (≥1 message)

## Data Flow

### Successful Task Processing

```
Client
  │
  └─> POST /tasks {title, description, priority, due_date}
      │
      └─> API Gateway
          │
          └─> API Lambda
              │
              ├─> Validate Input ✓
              ├─> Sanitize Data ✓
              ├─> Generate task_id (UUID)
              │
              └─> SQS FIFO Queue (MessageGroupId: "task-processing")
                  │
                  └─> Processor Lambda (triggered)
                      │
                      ├─> Parse Message ✓
                      ├─> Process Task ✓
                      └─> Delete Message ✓
                      
Client <─ 200 OK {task_id, message, status}
```

### Failed Task Processing with Retry

```
Processor Lambda
  │
  ├─> Attempt 1: Process Task ✗ (Error)
  │   └─> Message back to queue (visibility timeout)
  │
  ├─> Attempt 2: Process Task ✗ (Error)
  │   └─> Message back to queue (visibility timeout)
  │
  ├─> Attempt 3: Process Task ✗ (Error)
  │   └─> Message back to queue (visibility timeout)
  │
  └─> Max Receive Count Exceeded
      └─> Move to Dead Letter Queue
          └─> Trigger CloudWatch Alarm
```

## Ordering Guarantees

### How Ordering is Maintained

1. **Single Message Group**: All tasks use the same MessageGroupId
   - Ensures messages in the group are processed in exact order
   - Lambda only processes one batch per group at a time

2. **FIFO Queue Behavior**:
   - Messages are delivered in the exact order they are sent
   - No message from a group is processed until previous message is deleted or visibility timeout expires

3. **Batch Processing**:
   - Lambda receives batches of messages
   - Processes them sequentially within the function
   - Reports partial failures to maintain order

### Example: Concurrent Processing Scenario

```
Queue State:
├── Task A (Group: task-processing, Time: T0)
├── Task B (Group: task-processing, Time: T1)
├── Task C (Group: task-processing, Time: T2)
└── Task D (Group: task-processing, Time: T3)

Lambda Instance 1:
└─> Receives: [Task A, Task B, Task C] (batch size 3)
    ├─> Process A ✓
    ├─> Process B ✗ (failure)
    └─> Process C (not attempted - maintains order)

Result:
├─> A: Deleted (success)
├─> B: Returned to queue (failure, will retry)
└─> C: Returned to queue (not attempted, maintains order after B)

Next Invocation:
└─> Receives: [Task B, Task C, Task D]
    └─> Processing continues in order
```

## At-Least-Once Delivery

### Guarantees

1. **SQS Standard Behavior**: Messages remain in queue until explicitly deleted
2. **Visibility Timeout**: Messages become visible again if not processed in time
3. **Retry Logic**: Failed messages automatically retry (up to 3 times)
4. **DLQ**: Messages that fail all retries are preserved in DLQ

### Handling Duplicates

**Problem**: At-least-once delivery may result in duplicate processing.

**Solution**: Idempotent processing
- Use task_id as idempotency key
- Check if task already processed before applying changes
- Database operations use upsert/conditional writes

## Security Architecture

### IAM Roles and Permissions

**API Lambda Role**:
```
Permissions:
├─> sqs:SendMessage (Task Queue only)
├─> logs:CreateLogGroup
├─> logs:CreateLogStream
└─> logs:PutLogEvents
```

**Processor Lambda Role**:
```
Permissions:
├─> sqs:ReceiveMessage (Task Queue only)
├─> sqs:DeleteMessage (Task Queue only)
├─> sqs:GetQueueAttributes (Task Queue only)
├─> sqs:SendMessage (DLQ only)
├─> logs:CreateLogGroup
├─> logs:CreateLogStream
└─> logs:PutLogEvents
```

### Input Validation

**Validation Rules**:
- Title: Required, string, 1-200 characters
- Description: Required, string, 1-2000 characters
- Priority: Required, enum ["low", "medium", "high"]
- Due Date: Optional, ISO 8601 format

**Sanitization**:
- Trim whitespace
- Normalize case (priority to lowercase)
- Validate date format
- Escape special characters

## Scalability Considerations

### Current Limits

- **API Gateway**: 10,000 requests/second (default regional limit)
- **Lambda Concurrency**: 10 (reserved for processor), 1000 (account default)
- **SQS FIFO**: 300 messages/second (with batching: 3,000 messages/second)

### Scaling Strategy

**Vertical Scaling**:
- Increase Lambda memory/timeout
- Increase batch size (up to 10,000 for Lambda)

**Horizontal Scaling**:
- Multiple message groups (sacrifices global ordering)
- Multiple queues with routing (e.g., by priority)
- Increase reserved concurrency

## Cost Optimization

### Estimated Monthly Costs (1M tasks/month)

```
API Gateway: 1M requests = $3.50
Lambda (API): 1M invocations × 100ms × 256MB = $0.83
Lambda (Processor): 1M invocations × 500ms × 512MB = $8.35
SQS: 1M requests = $0.40
CloudWatch: Logs + Metrics = $5.00
────────────────────────────────────────
Total: ~$18.00/month
```

### Cost Optimization Tips

1. Batch processing (reduce Lambda invocations)
2. Optimize Lambda memory (pay for what you use)
3. Set log retention policies (don't keep logs forever)
4. Use CloudWatch metric filters (reduce custom metrics)

## Monitoring and Alerting

### Key Metrics

**API Lambda**:
- Invocations (count)
- Errors (count)
- Duration (ms)
- Throttles (count)

**Processor Lambda**:
- Invocations (count)
- Errors (count)
- Duration (ms)
- Concurrent Executions (count)

**SQS Queues**:
- Messages Visible (count)
- Messages Delayed (count)
- Age of Oldest Message (seconds)

**DLQ**:
- Messages Available (count) [Alert if > 0]

### Alarm Thresholds

- API Errors: > 5 in 5 minutes
- Processor Errors: > 10 in 5 minutes
- DLQ Messages: ≥ 1 message

## Disaster Recovery

### Backup Strategy

- **SQS Messages**: Retained for 4 days (configurable)
- **DLQ Messages**: Retained for 14 days
- **CloudWatch Logs**: Retained for 7 days

### Recovery Procedures

1. **API Lambda Failure**: 
   - API Gateway retries automatically
   - Messages safely stored in SQS

2. **Processor Lambda Failure**:
   - Messages return to queue after visibility timeout
   - Automatic retry (up to 3 attempts)
   - Manual replay from DLQ if needed

3. **Queue Corruption**:
   - Recreate queue from CDK
   - Messages in DLQ preserved

## Future Enhancements

1. **Multi-Region Deployment**: For higher availability
2. **API Authentication**: Add API keys or OAuth
3. **Priority Queues**: Separate queues per priority level
4. **Database Integration**: Persist tasks in DynamoDB
5. **Webhooks**: Notify external systems on completion
6. **Rate Limiting**: Protect against abuse
7. **Message Encryption**: KMS encryption for sensitive data

## References

- [AWS SQS FIFO Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html)
- [AWS Lambda Event Sources](https://docs.aws.amazon.com/lambda/latest/dg/invocation-eventsourcemapping.html)
- [CDK Best Practices](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html)
