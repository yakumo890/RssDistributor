from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_s3 as _s3,
    aws_dynamodb as _dynamodb,
    aws_secretsmanager as _secretsmanager,
    aws_scheduler as _scheduler,
    aws_scheduler_targets as _scheduler_targets,
    aws_logs as _cloudwatch_log,
    aws_iam as _iam,
    Duration,
    RemovalPolicy,
    TimeZone
)

from constructs import Construct
from .get_resource_ids_names import get_resource_ids_names

class RssDistributorStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, 
                 environment_name: str, 
                 bucket: _s3.Bucket, 
                 secrets: _secretsmanager.Secret, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        if environment_name == "dev":
            resource_ids, resource_names = get_resource_ids_names(True)
        else:
            resource_ids, resource_names = get_resource_ids_names(False)

        lambda_main_role = _iam.Role(self, resource_ids.lambda_main_role_id,
                                assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
                                role_name=resource_names.lambda_main_role_name)

        lambda_batch_role = _iam.Role(self, resource_ids.lambda_batch_role_id,
                                assumed_by=_iam.ServicePrincipal("lambda.amazonaws.com"),
                                role_name=resource_names.lambda_batch_role_name)

        article_table = _dynamodb.Table(self, resource_ids.article_table_id,
                                      table_name=resource_names.article_table_name,
                                      partition_key=_dynamodb.Attribute(name="source_url", type=_dynamodb.AttributeType.STRING),
                                      removal_policy=RemovalPolicy.DESTROY,
                                      billing_mode=_dynamodb.BillingMode.PAY_PER_REQUEST
        )

        term_table = _dynamodb.Table(self, resource_ids.term_table_id,
                                      table_name=resource_names.term_table_name,
                                      partition_key=_dynamodb.Attribute(name="term", type=_dynamodb.AttributeType.STRING),
                                      removal_policy=RemovalPolicy.DESTROY,
                                      billing_mode=_dynamodb.BillingMode.PAY_PER_REQUEST
        )

        dynamodb_policy = _iam.PolicyStatement(
            actions=["dynamodb:PutItem",
                     "dynamodb:UpdateItem",
                     "dynamodb:BatchWriteItem",
                     "dynamodb:Scan",
                     "dynamodb:Query",
                     "dynamodb:GetItem",
                     "dynamodb:BatchGetItem"],
                     resources=[article_table.table_arn, term_table.table_arn]
        )

        lambda_main_role.add_to_policy(dynamodb_policy)
        lambda_batch_role.add_to_policy(dynamodb_policy)

        bucket_policy = _iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"]
        )
        lambda_main_role.add_to_policy(bucket_policy)
        lambda_batch_role.add_to_policy(bucket_policy)

        secrets_policy = _iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"],
            resources=[secrets.secret_arn]
        )
        lambda_main_role.add_to_policy(secrets_policy)
        lambda_batch_role.add_to_policy(secrets_policy)

        log_group = _cloudwatch_log.LogGroup(self, resource_ids.log_group_id,
                                             log_group_name=resource_names.log_group_name,
                                             removal_policy=RemovalPolicy.DESTROY
        )

        log_group_policy = _iam.PolicyStatement(
            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
            resources=[log_group.log_group_arn, f"{log_group.log_group_arn}:*"]
        )
        lambda_main_role.add_to_policy(log_group_policy)
        lambda_batch_role.add_to_policy(log_group_policy)

        # SESについてはすでに存在するものを利用するので、ポリシーだけアタッチ
        ses_policy  = _iam.PolicyStatement(
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=[f"arn:aws:ses:{self.region}:{self.account}:identity/*"]
        )
        lambda_main_role.add_to_policy(ses_policy)

        rss_distributor_lambda_layer = _lambda.LayerVersion(self, resource_ids.lambda_layer_id,
                                                            layer_version_name=resource_names.lambda_layer_name,
                                                            code=_lambda.Code.from_asset("./lambda/.venv/lib/python3.12/site-packages/"),
                                                            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12]
        )

        rss_distributor_function = _lambda.Function(self, resource_ids.lambda_main_function_id,
                                                    function_name=resource_names.lambda_main_function_name,
                                                    runtime=_lambda.Runtime.PYTHON_3_12,
                                                    handler="lambda_function.lambda_handler",
                                                    timeout=Duration.minutes(15),
                                                    role=lambda_main_role,
                                                    code=_lambda.Code.from_inline("import boto3"),
                                                    log_group=log_group)
        rss_distributor_function.add_layers(rss_distributor_lambda_layer)

        _scheduler.Schedule(self, resource_ids.main_scheduler_id,
                            schedule_name=resource_names.main_scheduler_name,
                            schedule=_scheduler.ScheduleExpression.cron(minute="0", hour="23", day="*", month="*", year="*", time_zone=TimeZone.ASIA_TOKYO),
                            target=_scheduler_targets.LambdaInvoke(rss_distributor_function))
        
        batch_function = _lambda.Function(self, resource_ids.lambda_batch_function_id,
                                         function_name=resource_names.lambda_batch_function_name,
                                         runtime=_lambda.Runtime.PYTHON_3_12,
                                         handler="lambda_function.lambda_handler",
                                         timeout=Duration.minutes(15),
                                         role=lambda_batch_role,
                                         code=_lambda.Code.from_inline("import boto3"),
                                         log_group=log_group)
        batch_function.add_layers(rss_distributor_lambda_layer)

        _scheduler.Schedule(self, f"{resource_ids.batch_scheduler_id}",
                            schedule_name=f"{resource_names.batch_scheduler_name}",
                            schedule=_scheduler.ScheduleExpression.cron(minute="0", hour="0", day="*", month="*", year="*", time_zone=TimeZone.ASIA_TOKYO),
                            target=_scheduler_targets.LambdaInvoke(batch_function))