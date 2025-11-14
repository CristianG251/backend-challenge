import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface MonitoringStackProps extends cdk.StackProps {
  apiLambda: lambda.IFunction;
  processorLambda: lambda.IFunction;
  taskQueue: sqs.IQueue;
  deadLetterQueue: sqs.IQueue;
}

export class MonitoringStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    const { apiLambda, processorLambda, taskQueue, deadLetterQueue } = props;

    // BONUS: Create comprehensive CloudWatch Dashboard
    const dashboard = new cloudwatch.Dashboard(this, 'TaskManagementDashboard', {
      dashboardName: `task-management-dashboard`,
    });

    // API Lambda Metrics
    const apiErrorsMetric = apiLambda.metricErrors({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    const apiDurationMetric = apiLambda.metricDuration({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    const apiInvocationsMetric = apiLambda.metricInvocations({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    const apiThrottlesMetric = apiLambda.metricThrottles({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    // BONUS: API Lambda X-Ray metrics
    const apiTracesMetric = new cloudwatch.Metric({
      namespace: 'AWS/Lambda',
      metricName: 'TracedInvocations',
      dimensionsMap: {
        FunctionName: apiLambda.functionName,
      },
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    // Processor Lambda Metrics
    const processorErrorsMetric = processorLambda.metricErrors({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    const processorDurationMetric = processorLambda.metricDuration({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    const processorInvocationsMetric = processorLambda.metricInvocations({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    // Queue Metrics
    const queueMessagesMetric = taskQueue.metricApproximateNumberOfMessagesVisible({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    const queueAgeMetric = taskQueue.metricApproximateAgeOfOldestMessage({
      period: cdk.Duration.minutes(5),
      statistic: 'Maximum',
    });

    const dlqMessagesMetric = deadLetterQueue.metricApproximateNumberOfMessagesVisible({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    // BONUS: Add comprehensive dashboard widgets
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'API Lambda - Requests & Errors',
        left: [apiInvocationsMetric, apiErrorsMetric, apiThrottlesMetric],
        width: 12,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'API Lambda - Performance',
        left: [apiDurationMetric],
        right: [apiTracesMetric],
        width: 12,
        height: 6,
      })
    );

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Processor Lambda - Invocations & Errors',
        left: [processorInvocationsMetric, processorErrorsMetric],
        width: 12,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'Processor Lambda - Duration',
        left: [processorDurationMetric],
        width: 12,
        height: 6,
      })
    );

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Queue Depth & Age',
        left: [queueMessagesMetric],
        right: [queueAgeMetric],
        width: 12,
        height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'Dead Letter Queue Messages',
        left: [dlqMessagesMetric],
        width: 12,
        height: 6,
      })
    );

    // BONUS: Create comprehensive alarms
    
    // High error rate alarm
    new cloudwatch.Alarm(this, 'ApiLambdaErrorAlarm', {
      alarmName: `task-api-lambda-errors`,
      metric: apiErrorsMetric,
      threshold: 5,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when API Lambda has more than 5 errors in 5 minutes',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // High throttling alarm
    new cloudwatch.Alarm(this, 'ApiLambdaThrottleAlarm', {
      alarmName: `task-api-lambda-throttles`,
      metric: apiThrottlesMetric,
      threshold: 10,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when API Lambda is throttled more than 10 times',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Processor errors alarm
    new cloudwatch.Alarm(this, 'ProcessorLambdaErrorAlarm', {
      alarmName: `task-processor-lambda-errors`,
      metric: processorErrorsMetric,
      threshold: 10,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when Processor Lambda has more than 10 errors in 5 minutes',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // DLQ messages alarm
    new cloudwatch.Alarm(this, 'DLQMessagesAlarm', {
      alarmName: `task-dlq-messages`,
      metric: dlqMessagesMetric,
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      alarmDescription: 'Alert when messages appear in DLQ',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // BONUS: Queue depth alarm (queue backing up)
    new cloudwatch.Alarm(this, 'QueueDepthAlarm', {
      alarmName: `task-queue-depth-high`,
      metric: queueMessagesMetric,
      threshold: 100,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when queue has more than 100 messages for 10 minutes',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // BONUS: Message age alarm (messages not being processed fast enough)
    new cloudwatch.Alarm(this, 'MessageAgeAlarm', {
      alarmName: `task-message-age-high`,
      metric: queueAgeMetric,
      threshold: 300, // 5 minutes in seconds
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when oldest message is older than 5 minutes',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // BONUS: Create Log Insights queries
    const apiLogGroup = logs.LogGroup.fromLogGroupName(
      this,
      'ApiLogGroupRef',
      `/aws/lambda/task-api`
    );

    const processorLogGroup = logs.LogGroup.fromLogGroupName(
      this,
      'ProcessorLogGroupRef',
      `/aws/lambda/task-processor`
    );

    // Define useful Log Insights queries
    const errorQuery = new logs.QueryDefinition(this, 'ErrorLogsQuery', {
      queryDefinitionName: 'TaskManagement-ErrorLogs',
      queryString: new logs.QueryString({
        fields: ['@timestamp', '@message', 'level', 'error'],
        filter: 'level = "ERROR"',
        sort: '@timestamp desc',
        limit: 100,
      }),
      logGroups: [apiLogGroup, processorLogGroup],
    });

    const performanceQuery = new logs.QueryDefinition(this, 'PerformanceQuery', {
      queryDefinitionName: 'TaskManagement-Performance',
      queryString: new logs.QueryString({
        fields: ['@timestamp', 'functionName', 'duration', 'memoryUsed'],
        filter: 'ispresent(duration)',
        sort: 'duration desc',
        limit: 50,
      }),
      logGroups: [apiLogGroup, processorLogGroup],
    });

    const taskProcessingQuery = new logs.QueryDefinition(this, 'TaskProcessingQuery', {
      queryDefinitionName: 'TaskManagement-TaskProcessing',
      queryString: new logs.QueryString({
        fields: ['@timestamp', '@message', 'task_id', 'priority'],
        filter: '@message like /Processing task/ or @message like /Task created/',
        sort: '@timestamp desc',
        limit: 100,
      }),
      logGroups: [apiLogGroup, processorLogGroup],
    });

    // Output dashboard URL
    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL',
    });

    // Output X-Ray console URLs
    new cdk.CfnOutput(this, 'XRayServiceMapUrl', {
      value: `https://console.aws.amazon.com/xray/home?region=${this.region}#/service-map`,
      description: 'X-Ray Service Map URL',
    });

    new cdk.CfnOutput(this, 'XRayTracesUrl', {
      value: `https://console.aws.amazon.com/xray/home?region=${this.region}#/traces`,
      description: 'X-Ray Traces URL',
    });

    // Output Log Insights URL
    new cdk.CfnOutput(this, 'LogInsightsUrl', {
      value: `https://console.aws.amazon.com/cloudwatch/home?region=${this.region}#logsV2:logs-insights`,
      description: 'CloudWatch Logs Insights URL',
    });
  }
}
