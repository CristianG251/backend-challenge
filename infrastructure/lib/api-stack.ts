import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

export interface ApiStackProps extends cdk.StackProps {
  taskQueue: sqs.IQueue;
}

export class ApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly apiLambda: lambda.IFunction;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const { taskQueue } = props;

    // Create API Lambda function
    this.apiLambda = new lambda.Function(this, 'ApiLambda', {
      functionName: `task-api`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../src/api')),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        TASK_QUEUE_URL: taskQueue.queueUrl,
        LOG_LEVEL: 'INFO',
      },
      logGroup: new logs.LogGroup(this, 'ApiLogGroup', {
        logGroupName: `/aws/lambda/task-api`,
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // Grant Lambda permissions to send messages to queue
    taskQueue.grantSendMessages(this.apiLambda);

    // Create REST API
    this.api = new apigateway.RestApi(this, 'TaskApi', {
      restApiName: `task-management-api`,
      description: 'Task Management API',
      deployOptions: {
        stageName: 'prod',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: ['POST', 'OPTIONS'],
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
        maxAge: cdk.Duration.days(1),
      },
    });

    // Create /tasks resource
    const tasksResource = this.api.root.addResource('tasks');

    // Add POST /tasks endpoint
    const createTaskIntegration = new apigateway.LambdaIntegration(this.apiLambda, {
      proxy: true,
      integrationResponses: [
        {
          statusCode: '200',
        },
        {
          statusCode: '400',
          selectionPattern: '.*"statusCode":400.*',
        },
        {
          statusCode: '500',
          selectionPattern: '.*"statusCode":500.*',
        },
      ],
    });

    tasksResource.addMethod('POST', createTaskIntegration, {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
        {
          statusCode: '400',
          responseModels: {
            'application/json': apigateway.Model.ERROR_MODEL,
          },
        },
        {
          statusCode: '500',
          responseModels: {
            'application/json': apigateway.Model.ERROR_MODEL,
          },
        },
      ],
    });

    // Output API endpoint
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.api.url,
      description: 'API Gateway Endpoint URL',
      exportName: `ApiEndpoint`,
    });

    new cdk.CfnOutput(this, 'ApiId', {
      value: this.api.restApiId,
      description: 'API Gateway ID',
      exportName: `ApiId`,
    });

    new cdk.CfnOutput(this, 'ApiLambdaArn', {
      value: this.apiLambda.functionArn,
      description: 'API Lambda ARN',
      exportName: `ApiLambdaArn`,
    });
  }
}
