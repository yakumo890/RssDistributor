from aws_cdk import (
    Stack,
    aws_s3 as _s3,
    aws_secretsmanager as _secretsmanager,
    RemovalPolicy,
)

from constructs import Construct
from .get_common_resource_ids_names import get_common_resource_ids_names

class RssDistributorCommonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        common_resource_ids, common_resource_names = get_common_resource_ids_names()

        self.bucket = _s3.Bucket(self, common_resource_ids.bucket_id,
                            bucket_name=common_resource_names.bucket_name,
                            auto_delete_objects=True,
                            block_public_access=_s3.BlockPublicAccess.BLOCK_ALL,
                            removal_policy=RemovalPolicy.DESTROY
        )

        self.secrets_manager = _secretsmanager.Secret(self, common_resource_ids.secrets_id,
                                                 secret_name=common_resource_names.secrets_name,
                                                 removal_policy=RemovalPolicy.DESTROY
        )