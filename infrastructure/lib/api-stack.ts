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
  public readonly apiKey: apigateway.IApiKey;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const { taskQueue } = props;

    // Create API Lambda function with X-Ray tracing enabled
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
      // BONUS: Enable X-Ray distributed tracing
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant Lambda permissions to send messages to queue
    taskQueue.grantSendMessages(this.apiLambda);

    // Create REST API with request validation
    this.api = new apigateway.RestApi(this, 'TaskApi', {
      restApiName: `task-management-api`,
      description: 'Task Management API with Authentication',
      deployOptions: {
        stageName: 'prod',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
        // BONUS: Enable X-Ray tracing for API Gateway
        tracingEnabled: true,
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

    // BONUS FEATURE 1: API Authentication with API Key
    this.apiKey = this.api.addApiKey('TaskApiKey', {
      apiKeyName: `task-api-key`,
      description: 'API Key for Task Management API',
    });

    // BONUS FEATURE 4: Rate Limiting and Throttling
    const usagePlan = this.api.addUsagePlan('TaskUsagePlan', {
      name: 'Task Management Usage Plan',
      description: 'Usage plan with rate limiting and quotas',
      throttle: {
        rateLimit: 100,      // 100 requests per second
        burstLimit: 200,     // Allow bursts up to 200
      },
      quota: {
        limit: 10000,        // 10,000 requests per month
        period: apigateway.Period.MONTH,
      },
    });

    // Associate API key with usage plan
    usagePlan.addApiKey(this.apiKey);
    usagePlan.addApiStage({
      stage: this.api.deploymentStage,
    });

    // Create request validator for strict validation
    const requestValidator = new apigateway.RequestValidator(this, 'TaskRequestValidator', {
      restApi: this.api,
      requestValidatorName: 'task-request-validator',
      validateRequestBody: true,
      validateRequestParameters: true,
    });

    // Create request model for validation
    const taskModel = new apigateway.Model(this, 'TaskModel', {
      restApi: this.api,
      contentType: 'application/json',
      description: 'Task creation request model',
      modelName: 'TaskModel',
      schema: {
        type: apigateway.JsonSchemaType.OBJECT,
        required: ['title', 'description', 'priority'],
        properties: {
          title: {
            type: apigateway.JsonSchemaType.STRING,
            minLength: 1,
            maxLength: 200,
          },
          description: {
            type: apigateway.JsonSchemaType.STRING,
            minLength: 1,
            maxLength: 2000,
          },
          priority: {
            type: apigateway.JsonSchemaType.STRING,
            enum: ['low', 'medium', 'high'],
          },
          due_date: {
            type: apigateway.JsonSchemaType.STRING,
            pattern: '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$',
          },
        },
      },
    });

    // Create /tasks resource
    const tasksResource = this.api.root.addResource('tasks');

    // Add POST /tasks endpoint with authentication and validation
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
      // BONUS: Require API Key for authentication
      apiKeyRequired: true,
      requestValidator: requestValidator,
      requestModels: {
        'application/json': taskModel,
      },
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

    // Output API endpoint and API key
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

    // BONUS: Output API Key ID for retrieval
    new cdk.CfnOutput(this, 'ApiKeyId', {
      value: this.apiKey.keyId,
      description: 'API Key ID (use AWS Console or CLI to get the actual key value)',
      exportName: `ApiKeyId`,
    });

    // Add instructions for getting the API key value
    new cdk.CfnOutput(this, 'ApiKeyRetrievalCommand', {
      value: `aws apigateway get-api-key --api-key ${this.apiKey.keyId} --include-value --query 'value' --output text`,
      description: 'Command to retrieve API Key value',
    });
  }
}
