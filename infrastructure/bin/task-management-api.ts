#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ApiStack } from '../lib/api-stack';
import { QueueStack } from '../lib/queue-stack';
import { MonitoringStack } from '../lib/monitoring-stack';

const app = new cdk.App();

// Get environment configuration from context or environment variables
const environment = app.node.tryGetContext('environment') || process.env.ENVIRONMENT || 'dev';
const region = app.node.tryGetContext('region') || process.env.AWS_REGION || 'us-east-1';

// Define stack naming prefix
const stackPrefix = `TaskManagement-${environment}`;

// Create Queue Stack first (foundational infrastructure)
const queueStack = new QueueStack(app, `${stackPrefix}-QueueStack`, {
  env: {
    region: region,
  },
  stackName: `${stackPrefix}-QueueStack`,
  description: 'Task Management Queue Infrastructure',
  tags: {
    Environment: environment,
    Application: 'TaskManagement',
    ManagedBy: 'CDK',
  },
});

// Create API Stack (depends on Queue Stack)
const apiStack = new ApiStack(app, `${stackPrefix}-ApiStack`, {
  env: {
    region: region,
  },
  stackName: `${stackPrefix}-ApiStack`,
  description: 'Task Management API Infrastructure',
  taskQueue: queueStack.taskQueue,
  tags: {
    Environment: environment,
    Application: 'TaskManagement',
    ManagedBy: 'CDK',
  },
});

// Create Monitoring Stack
const monitoringStack = new MonitoringStack(app, `${stackPrefix}-MonitoringStack`, {
  env: {
    region: region,
  },
  stackName: `${stackPrefix}-MonitoringStack`,
  description: 'Task Management Monitoring Infrastructure',
  apiLambda: apiStack.apiLambda,
  processorLambda: queueStack.processorLambda,
  taskQueue: queueStack.taskQueue,
  deadLetterQueue: queueStack.deadLetterQueue,
  tags: {
    Environment: environment,
    Application: 'TaskManagement',
    ManagedBy: 'CDK',
  },
});

app.synth();
