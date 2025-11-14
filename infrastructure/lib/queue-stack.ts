import * as cdk from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

export class QueueStack extends cdk.Stack {
  public readonly taskQueue: sqs.IQueue;
  public readonly deadLetterQueue: sqs.IQueue;
  public readonly processorLambda: lambda.IFunction;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create Dead Letter Queue (DLQ) for failed messages
    this.deadLetterQueue = new sqs.Queue(this, 'TaskDLQ', {
      queueName: `task-dlq.fifo`,
      fifo: true,
      contentBasedDeduplication: true,
      retentionPeriod: cdk.Duration.days(14),
      visibilityTimeout: cdk.Duration.seconds(300),
    });

    // Create main FIFO queue with ordering guarantees
    this.taskQueue = new sqs.Queue(this, 'TaskQueue', {
      queueName: `task-queue.fifo`,
      fifo: true,
      contentBasedDeduplication: true,
      visibilityTimeout: cdk.Duration.seconds(300),
      receiveMessageWaitTime: cdk.Duration.seconds(20),
      retentionPeriod: cdk.Duration.days(4),
      deadLetterQueue: {
        queue: this.deadLetterQueue,
        maxReceiveCount: 3,
      },
    });

    // Create processor Lambda function
    this.processorLambda = new lambda.Function(this, 'ProcessorLambda', {
      functionName: `task-processor`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../src/queue_processor')),
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        TASK_QUEUE_URL: this.taskQueue.queueUrl,
        DLQ_URL: this.deadLetterQueue.queueUrl,
        LOG_LEVEL: 'INFO',
      },
      logGroup: new logs.LogGroup(this, 'ProcessorLogGroup', {
        logGroupName: `/aws/lambda/task-processor`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
      reservedConcurrentExecutions: 10,
    });

    // Grant Lambda permissions to read from queue
    this.taskQueue.grantConsumeMessages(this.processorLambda);
    this.deadLetterQueue.grantSendMessages(this.processorLambda);

    // Configure SQS as Lambda event source with batching
    const eventSource = new lambdaEventSources.SqsEventSource(this.taskQueue, {
      batchSize: 10,
      // Note: maxBatchingWindow not supported for FIFO queues
      reportBatchItemFailures: true,
    });

    this.processorLambda.addEventSource(eventSource);

    // Output queue URLs
    new cdk.CfnOutput(this, 'TaskQueueUrl', {
      value: this.taskQueue.queueUrl,
      description: 'Task Queue URL',
      exportName: `TaskQueueUrl`,
    });

    new cdk.CfnOutput(this, 'TaskQueueArn', {
      value: this.taskQueue.queueArn,
      description: 'Task Queue ARN',
      exportName: `TaskQueueArn`,
    });

    new cdk.CfnOutput(this, 'DLQUrl', {
      value: this.deadLetterQueue.queueUrl,
      description: 'Dead Letter Queue URL',
      exportName: `DLQUrl`,
    });

    new cdk.CfnOutput(this, 'ProcessorLambdaArn', {
      value: this.processorLambda.functionArn,
      description: 'Processor Lambda ARN',
      exportName: `ProcessorLambdaArn`,
    });
  }
}
