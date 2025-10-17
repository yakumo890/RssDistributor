class CommonResourceIds:
    def __init__(self, bucket_id: str, secrets_id: str):
        self.bucket_id = bucket_id
        self.secrets_id = secrets_id

    def get_common_resource_ids():
        bucket_id: str = "RssDistributorBucket"
        secrets_id: str = "RssDistributorSecrets"
        return CommonResourceIds(bucket_id=bucket_id, secrets_id=secrets_id)
    
class CommonResourceNames:
    def __init__(self, bucket_name: str, secrets_name: str):
        self.bucket_name = bucket_name
        self.secrets_name = secrets_name

    def get_common_resource_names():
        bucket_name: str = "rss-distributor-bucket"
        secrets_name: str = "rss_distributor_secrets"
        return CommonResourceNames(bucket_name=bucket_name, secrets_name=secrets_name)
    
def get_common_resource_ids_names():
    return CommonResourceIds.get_common_resource_ids(), CommonResourceNames.get_common_resource_names()