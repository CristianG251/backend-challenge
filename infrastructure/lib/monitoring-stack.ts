import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sqs from 'aws-cdk-lib/aws-sqs';
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

    // Create CloudWatch Dashboard
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

    // Processor Lambda Metrics
    const processorErrorsMetric = processorLambda.metricErrors({
      period: cdk.Duration.minutes(5),
      statistic: 'Sum',
    });

    const processorDurationMetric = processorLambda.metricDuration({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    // Queue Metrics
    const queueMessagesMetric = taskQueue.metricApproximateNumberOfMessagesVisible({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    const dlqMessagesMetric = deadLetterQueue.metricApproximateNumberOfMessagesVisible({
      period: cdk.Duration.minutes(5),
      statistic: 'Average',
    });

    // Add widgets to dashboard
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'API Lambda Metrics',
        left: [apiInvocationsMetric, apiErrorsMetric],
        right: [apiDurationMetric],
      })
    );

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Processor Lambda Metrics',
        left: [processorErrorsMetric],
        right: [processorDurationMetric],
      })
    );

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Queue Metrics',
        left: [queueMessagesMetric, dlqMessagesMetric],
      })
    );

    // Create alarms
    new cloudwatch.Alarm(this, 'ApiLambdaErrorAlarm', {
      alarmName: `task-api-lambda-errors`,
      metric: apiErrorsMetric,
      threshold: 5,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when API Lambda has more than 5 errors in 5 minutes',
    });

    new cloudwatch.Alarm(this, 'ProcessorLambdaErrorAlarm', {
      alarmName: `task-processor-lambda-errors`,
      metric: processorErrorsMetric,
      threshold: 10,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Alert when Processor Lambda has more than 10 errors in 5 minutes',
    });

    new cloudwatch.Alarm(this, 'DLQMessagesAlarm', {
      alarmName: `task-dlq-messages`,
      metric: dlqMessagesMetric,
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      alarmDescription: 'Alert when messages appear in DLQ',
    });

    // Output dashboard URL
    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${dashboard.dashboardName}`,
      description: 'CloudWatch Dashboard URL',
    });
  }
}
