# Deployment Guide

This guide covers deploying the Task Management API to AWS using AWS CDK.

## Prerequisites

### Required Software

- Node.js >= 18.x
- Python >= 3.12
- npm >= 9.x
- AWS CLI >= 2.x (optional but recommended)

### AWS Account

- Active AWS account
- IAM user with appropriate permissions
- AWS CLI configured with credentials

## Quick Start

### 1. Validate Infrastructure (Required for Evaluation)

This step validates that the CDK code synthesizes correctly without deploying:

```bash
# Navigate to infrastructure directory
cd infrastructure

# Install dependencies
npm install

# Build TypeScript
npm run build

# Synthesize CloudFormation templates
npx cdk synth
```

**Expected Output**:
```
Successfully synthesized to /path/to/infrastructure/cdk.out
Supply a stack id (TaskManagement-dev-QueueStack, TaskManagement-dev-ApiStack, TaskManagement-dev-MonitoringStack) to display its template.
```

This generates CloudFormation templates in `infrastructure/cdk.out/`:
- `TaskManagement-dev-QueueStack.template.json`
- `TaskManagement-dev-ApiStack.template.json`
- `TaskManagement-dev-MonitoringStack.template.json`

### 2. Deploy to AWS (Optional)

If you want to actually deploy to AWS:

```bash
# Configure AWS credentials (if not already done)
aws configure

# Bootstrap CDK (first time only)
cd infrastructure
npx cdk bootstrap

# Deploy all stacks
npx cdk deploy --all

# Or deploy stacks individually
npx cdk deploy TaskManagement-dev-QueueStack
npx cdk deploy TaskManagement-dev-ApiStack
npx cdk deploy TaskManagement-dev-MonitoringStack
```

## Environment Configuration

### Environment Variables

The following environment variables can be set:

```bash
# Set environment (dev, staging, prod)
export ENVIRONMENT=dev

# Set AWS region
export AWS_REGION=us-east-1

# AWS credentials (if not using AWS CLI config)
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
```

### CDK Context

You can also pass values via CDK context:

```bash
npx cdk deploy --context environment=dev --context region=us-east-1
```

## Detailed Deployment Steps

### Step 1: Install Dependencies

```bash
# Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node.js dependencies (CDK)
cd infrastructure
npm install
cd ..
```

### Step 2: Build and Validate

```bash
# Build TypeScript
cd infrastructure
npm run build

# Validate with TypeScript compiler
npm run build

# Validate with ESLint
npm run lint

# Synthesize CloudFormation
npx cdk synth
```

### Step 3: Bootstrap CDK (First Time Only)

CDK bootstrap creates required S3 buckets and IAM roles:

```bash
npx cdk bootstrap aws://ACCOUNT-ID/REGION

# Example:
npx cdk bootstrap aws://123456789012/us-east-1
```

### Step 4: Review Changes

See what will be deployed:

```bash
npx cdk diff
```

### Step 5: Deploy

Deploy all stacks:

```bash
npx cdk deploy --all
```

Or deploy stacks individually:

```bash
# Deploy in order (Queue stack first, then API)
npx cdk deploy TaskManagement-dev-QueueStack
npx cdk deploy TaskManagement-dev-ApiStack
npx cdk deploy TaskManagement-dev-MonitoringStack
```

### Step 6: Get Outputs

After deployment, note the stack outputs:

```bash
# API endpoint
aws cloudformation describe-stacks \
  --stack-name TaskManagement-dev-ApiStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text

# Queue URLs
aws cloudformation describe-stacks \
  --stack-name TaskManagement-dev-QueueStack \
  --query 'Stacks[0].Outputs'
```

## Testing Deployed API

### Using curl

```bash
# Get API endpoint from outputs
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name TaskManagement-dev-ApiStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

# Create a task
curl -X POST "${API_ENDPOINT}tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Task",
    "description": "Testing deployed API",
    "priority": "high",
    "due_date": "2025-12-31T23:59:59Z"
  }'
```

Expected response:
```json
{
  "task_id": "12345678-1234-1234-1234-123456789012",
  "message": "Task created successfully",
  "status": "queued"
}
```

### Using Postman

1. Import the API endpoint from CloudFormation outputs
2. Create a POST request to `{API_ENDPOINT}/tasks`
3. Set headers:
   - `Content-Type: application/json`
4. Set body:
```json
{
  "title": "Postman Test",
  "description": "Testing from Postman",
  "priority": "medium"
}
```

## Monitoring Deployed System

### CloudWatch Dashboard

Access the dashboard:
```bash
# Get dashboard URL from outputs
aws cloudformation describe-stacks \
  --stack-name TaskManagement-dev-MonitoringStack \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardUrl`].OutputValue' \
  --output text
```

Or navigate to:
`AWS Console → CloudWatch → Dashboards → task-management-dashboard`

### View Logs

```bash
# API Lambda logs
aws logs tail /aws/lambda/task-api --follow

# Processor Lambda logs
aws logs tail /aws/lambda/task-processor --follow
```

### Check Queue Status

```bash
# Get queue URL
QUEUE_URL=$(aws cloudformation describe-stacks \
  --stack-name TaskManagement-dev-QueueStack \
  --query 'Stacks[0].Outputs[?OutputKey==`TaskQueueUrl`].OutputValue' \
  --output text)

# Get queue attributes
aws sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names All
```

## Updating Deployed Stacks

### Update Lambda Code

After changing Python code:

```bash
cd infrastructure
npx cdk deploy TaskManagement-dev-ApiStack    # If API code changed
npx cdk deploy TaskManagement-dev-QueueStack  # If processor code changed
```

### Update Infrastructure

After changing CDK code:

```bash
cd infrastructure
npm run build
npx cdk diff    # Review changes
npx cdk deploy --all
```

## Destroying Resources

### Destroy All Stacks

```bash
cd infrastructure
npx cdk destroy --all
```

### Destroy Individual Stacks

Destroy in reverse order:

```bash
npx cdk destroy TaskManagement-dev-MonitoringStack
npx cdk destroy TaskManagement-dev-ApiStack
npx cdk destroy TaskManagement-dev-QueueStack
```

### Manual Cleanup

Some resources may require manual deletion:

1. CloudWatch Log Groups (if retention policy set)
2. S3 buckets (if created outside CDK)

## Troubleshooting

### CDK Synth Fails

**Error**: `Cannot find module 'aws-cdk-lib'`

**Solution**:
```bash
cd infrastructure
npm install
```

### CDK Deploy Fails

**Error**: `Stack is in UPDATE_ROLLBACK_COMPLETE state`

**Solution**:
```bash
# Delete the stack and redeploy
npx cdk destroy StackName
npx cdk deploy StackName
```

### Lambda Function Errors

**Error**: Function returns 500 errors

**Solution**:
1. Check CloudWatch Logs
2. Verify environment variables
3. Check IAM permissions
4. Review Lambda code changes

### SQS Permission Errors

**Error**: `Access Denied` when sending messages

**Solution**:
Check IAM role has correct permissions:
```bash
aws iam get-role-policy \
  --role-name TaskManagement-dev-ApiStack-ApiLambdaRole \
  --policy-name sqs-policy
```

## Security Best Practices

### 1. Use IAM Roles

Never use IAM user credentials in Lambda:
```typescript
// Good - uses execution role
const sqs = new aws.SQS();

// Bad - hardcoded credentials
const sqs = new aws.SQS({
  accessKeyId: 'AKIAIOSFODNN7EXAMPLE',
  secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
});
```

### 2. Enable Encryption

For production:
```typescript
new sqs.Queue(this, 'TaskQueue', {
  encryption: sqs.QueueEncryption.KMS,
  encryptionMasterKey: kmsKey,
});
```

### 3. Restrict API Access

Add authorization:
```typescript
tasksResource.addMethod('POST', integration, {
  authorizationType: apigateway.AuthorizationType.IAM,
  // or
  authorizer: new apigateway.TokenAuthorizer(...)
});
```

### 4. Enable API Throttling

```typescript
new apigateway.RestApi(this, 'TaskApi', {
  deployOptions: {
    throttlingBurstLimit: 100,
    throttlingRateLimit: 50,
  },
});
```

## Cost Optimization

### Estimated Costs

For 1 million tasks per month:
- API Gateway: $3.50
- Lambda: $9.18
- SQS: $0.40
- CloudWatch: $5.00
- **Total: ~$18.00/month**

### Reduce Costs

1. Increase batch size (reduce Lambda invocations)
2. Optimize Lambda memory allocation
3. Set log retention policies
4. Use Reserved Concurrency only when needed

## Production Checklist

Before deploying to production:

- [ ] Enable CloudWatch Logs retention
- [ ] Set up CloudWatch Alarms with SNS notifications
- [ ] Enable API Gateway access logging
- [ ] Configure DLQ alarm actions
- [ ] Enable SQS encryption (KMS)
- [ ] Add API authentication
- [ ] Set up backup/disaster recovery
- [ ] Document API endpoints
- [ ] Create runbooks for common issues
- [ ] Set up cost alerts
- [ ] Configure auto-scaling if needed
- [ ] Enable X-Ray tracing for debugging

## Multi-Region Deployment

For high availability:

```bash
# Deploy to multiple regions
export AWS_REGION=us-east-1
npx cdk deploy --all

export AWS_REGION=eu-west-1
npx cdk deploy --all
```

Configure Route53 for failover between regions.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - uses: actions/setup-python@v4
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          cd infrastructure && npm install
      
      - name: Run tests
        run: pytest
      
      - name: Deploy
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          cd infrastructure
          npx cdk deploy --all --require-approval never
```

## Support

For deployment issues:
1. Check CloudFormation events in AWS Console
2. Review CloudWatch Logs
3. Verify IAM permissions
4. Check CDK version compatibility

## Additional Resources

- [AWS CDK Workshop](https://cdkworkshop.com/)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [SQS FIFO Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html)
