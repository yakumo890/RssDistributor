class ResourceIds:
    def __init__(self, lambda_role_id: str, article_table_id: str, term_table_id: str,
                 log_group_id: str, lambda_layer_id: str, lambda_function_id: str,
                 scheduler_id: str):
        self.lambda_role_id = lambda_role_id
        self.article_table_id = article_table_id
        self.term_table_id = term_table_id
        self.log_group_id = log_group_id
        self.lambda_layer_id = lambda_layer_id
        self.lambda_function_id = lambda_function_id
        self.scheduler_id = scheduler_id

    def get_resource_ids():
        lambda_role_id: str = "RssDistributorLambdaRole"
        article_table_id: str = "RssDistributorArticle"
        term_table_id: str = "RssDistributorTerm"
        log_group_id: str = "RssDistributorLogGroup"
        lambda_layer_id: str = "RssDistributorLambdaLayer"
        lambda_function_id: str = "RssDistributor"
        scheduler_id: str = "RssDistributorScheduler"
        return ResourceIds(lambda_role_id=lambda_role_id, article_table_id=article_table_id,
                           term_table_id=term_table_id, log_group_id=log_group_id,
                           lambda_layer_id=lambda_layer_id, lambda_function_id=lambda_function_id,
                           scheduler_id=scheduler_id)

    def get_resource_dev_ids():
        lambda_role_id: str = "RssDistributorLambdaRoleDev"
        article_table_id: str = "RssDistributorArticleDev"
        term_table_id: str = "RssDistributorTermDev"
        log_group_id: str = "RssDistributorLogGroupDev"
        lambda_layer_id: str = "RssDistributorLambdaLayerDev"
        lambda_function_id: str = "RssDistributorDev"
        scheduler_id: str = "RssDistributorSchedulerDev"
        return ResourceIds(lambda_role_id=lambda_role_id, article_table_id=article_table_id,
                           term_table_id=term_table_id, log_group_id=log_group_id,
                           lambda_layer_id=lambda_layer_id, lambda_function_id=lambda_function_id,
                           scheduler_id=scheduler_id)

class ResourceNames:
    def __init__(self, lambda_role_name: str, article_table_name: str, term_table_name: str,
                 log_group_name: str, lambda_function_name: str, lambda_layer_name: str, scheduler_name: str):
            self.lambda_role_name = lambda_role_name
            self.article_table_name = article_table_name
            self.term_table_name = term_table_name
            self.log_group_name = log_group_name
            self.lambda_function_name = lambda_function_name
            self.lambda_layer_name = lambda_layer_name
            self.scheduler_name = scheduler_name

    def get_resource_names():
        lambda_role_name: str = "RssDistributorLambdaRole"
        article_table_name: str = "rss_distributor_article"
        term_table_name: str = "rss_distributor_term"
        log_group_name: str = "/aws/lambda/RssDistributorLogGroup"
        lambda_function_name: str = "RssDistributor"
        lambda_layer_name: str = "RssDistributorLayer"
        scheduler_name: str = "RssDistributorScheduler"
        return ResourceNames(lambda_role_name=lambda_role_name, article_table_name=article_table_name,
                             term_table_name=term_table_name, log_group_name=log_group_name,
                             lambda_function_name=lambda_function_name, lambda_layer_name=lambda_layer_name,
                             scheduler_name=scheduler_name)

    def get_resource_dev_names():
        lambda_role_name = "RssDistributorLambdaRoleDev"
        article_table_name = "rss_distributor_article_dev"
        term_table_name = "rss_distributor_term_dev"
        log_group_name = "/aws/lambda/RssDistributorLogGroupDev"
        lambda_function_name = "RssDistributorDev"
        lambda_layer_name = "RssDistributorLayerDev"
        scheduler_name = "RssDistributorSchedulerDev"
        return ResourceNames(lambda_role_name=lambda_role_name, article_table_name=article_table_name,
                             term_table_name=term_table_name, log_group_name=log_group_name,
                             lambda_function_name=lambda_function_name, lambda_layer_name=lambda_layer_name,
                             scheduler_name=scheduler_name)

def get_resource_ids_names(is_dev: bool = False):
    if is_dev:
        return ResourceIds.get_resource_dev_ids(), ResourceNames.get_resource_dev_names()
    else:
        return ResourceIds.get_resource_ids(), ResourceNames.get_resource_names()
