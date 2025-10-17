#!/usr/bin/env python3
import os

import aws_cdk as cdk

from rss_distributor.rss_distributor_stack import RssDistributorStack
from rss_distributor.rss_distributor_common_stack import RssDistributorCommonStack

app = cdk.App()

account_id = os.environ.get('AWS_ACCOUNT_ID')
region = os.environ.get('AWS_REGION', 'ap-northeast-1')
environment_name = app.node.try_get_context("env") or "prod"

if environment_name == "dev":
    stack_id = "RssDistributorDevStack"
else:
    stack_id = "RssDistributorStack"

common_stack = RssDistributorCommonStack(app, "RssDistributorCommonStack",
                    env=cdk.Environment(account=account_id, region=region))

RssDistributorStack(app, stack_id,
                    env=cdk.Environment(account=account_id, region=region),
                    environment_name=environment_name,
                    bucket=common_stack.bucket,
                    secrets=common_stack.secrets_manager)

app.synth()
