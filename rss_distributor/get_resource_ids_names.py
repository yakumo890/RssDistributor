class ResourceIds:
    def __init__(self, lambda_main_role_id: str, lambda_batch_role_id: str, article_table_id: str, term_table_id: str,
                 log_group_id: str, lambda_layer_id: str, lambda_main_function_id: str, lambda_batch_function_id: str,
                 main_scheduler_id: str, batch_scheduler_id: str):
        self.lambda_main_role_id = lambda_main_role_id
        self.lambda_batch_role_id = lambda_batch_role_id
        self.article_table_id = article_table_id
        self.term_table_id = term_table_id
        self.log_group_id = log_group_id
        self.lambda_layer_id = lambda_layer_id
        self.lambda_main_function_id = lambda_main_function_id
        self.lambda_batch_function_id = lambda_batch_function_id
        self.main_scheduler_id = main_scheduler_id
        self.batch_scheduler_id = batch_scheduler_id

    def get_resource_ids():
        lambda_main_role_id: str = "RssDistributorLambdaRole"
        lambda_batch_role_id: str = "RssDistributorBatchLambdaRole"
        article_table_id: str = "RssDistributorArticle"
        term_table_id: str = "RssDistributorTerm"
        log_group_id: str = "RssDistributorLogGroup"
        lambda_layer_id: str = "RssDistributorLambdaLayer"
        lambda_main_function_id: str = "RssDistributor"
        lambda_batch_function_id: str = "RssDistributorBatch"
        main_scheduler_id: str = "RssDistributorScheduler"
        batch_scheduler_id: str = "RssDistributorBatchScheduler"
        return ResourceIds(lambda_main_role_id=lambda_main_role_id, lambda_batch_role_id=lambda_batch_role_id, article_table_id=article_table_id,
                           term_table_id=term_table_id, log_group_id=log_group_id,
                           lambda_layer_id=lambda_layer_id, lambda_main_function_id=lambda_main_function_id,
                           lambda_batch_function_id=lambda_batch_function_id, main_scheduler_id=main_scheduler_id,
                           batch_scheduler_id=batch_scheduler_id)

    def get_resource_dev_ids():
        lambda_main_role_id: str = "RssDistributorLambdaRoleDev"
        lambda_batch_role_id: str = "RssDistributorBatchLambdaRoleDev"
        article_table_id: str = "RssDistributorArticleDev"
        term_table_id: str = "RssDistributorTermDev"
        log_group_id: str = "RssDistributorLogGroupDev"
        lambda_layer_id: str = "RssDistributorLambdaLayerDev"
        lambda_main_function_id: str = "RssDistributorDev"
        lambda_batch_function_id: str = "RssDistributorBatchDev"
        main_scheduler_id: str = "RssDistributorSchedulerDev"
        batch_scheduler_id: str = "RssDistributorBatchSchedulerDev"
        return ResourceIds(lambda_main_role_id=lambda_main_role_id, lambda_batch_role_id=lambda_batch_role_id, article_table_id=article_table_id,
                           term_table_id=term_table_id, log_group_id=log_group_id,
                           lambda_layer_id=lambda_layer_id, lambda_main_function_id=lambda_main_function_id,
                           lambda_batch_function_id=lambda_batch_function_id, main_scheduler_id=main_scheduler_id,
                           batch_scheduler_id=batch_scheduler_id)

class ResourceNames:
    def __init__(self, lambda_main_role_name: str, lambda_batch_role_name: str, article_table_name: str, term_table_name: str,
                 log_group_name: str, lambda_main_function_name: str, lambda_batch_function_name: str, lambda_layer_name: str, main_scheduler_name: str, batch_scheduler_name: str):
            self.lambda_main_role_name = lambda_main_role_name
            self.lambda_batch_role_name = lambda_batch_role_name
            self.article_table_name = article_table_name
            self.term_table_name = term_table_name
            self.log_group_name = log_group_name
            self.lambda_main_function_name = lambda_main_function_name
            self.lambda_batch_function_name = lambda_batch_function_name
            self.lambda_layer_name = lambda_layer_name
            self.main_scheduler_name = main_scheduler_name
            self.batch_scheduler_name = batch_scheduler_name

    def get_resource_names():
        lambda_main_role_name: str = "RssDistributorLambdaRole"
        lambda_batch_role_name: str = "RssDistributorBatchLambdaRole"
        article_table_name: str = "rss_distributor_article"
        term_table_name: str = "rss_distributor_term"
        log_group_name: str = "/aws/lambda/RssDistributorLogGroup"
        lambda_main_function_name: str = "RssDistributor"
        lambda_batch_function_name: str = "RssDistributorBatch"
        lambda_layer_name: str = "RssDistributorLayer"
        main_scheduler_name: str = "RssDistributorScheduler"
        batch_scheduler_name: str = "RssDistributorBatchScheduler"
        return ResourceNames(lambda_main_role_name=lambda_main_role_name, lambda_batch_role_name=lambda_batch_role_name,
                             article_table_name=article_table_name, term_table_name=term_table_name,
                             log_group_name=log_group_name, lambda_main_function_name=lambda_main_function_name,
                             lambda_batch_function_name=lambda_batch_function_name, lambda_layer_name=lambda_layer_name,
                             main_scheduler_name=main_scheduler_name, batch_scheduler_name=batch_scheduler_name)

    def get_resource_dev_names():
        lambda_main_role_name = "RssDistributorLambdaRoleDev"
        lambda_batch_role_name = "RssDistributorBatchLambdaRoleDev"
        article_table_name = "rss_distributor_article_dev"
        term_table_name = "rss_distributor_term_dev"
        log_group_name = "/aws/lambda/RssDistributorLogGroupDev"
        lambda_main_function_name = "RssDistributorDev"
        lambda_batch_function_name = "RssDistributorBatchDev"
        lambda_layer_name = "RssDistributorLayerDev"
        main_scheduler_name = "RssDistributorSchedulerDev"
        batch_scheduler_name = "RssDistributorBatchSchedulerDev"    
        return ResourceNames(lambda_main_role_name=lambda_main_role_name, lambda_batch_role_name=lambda_batch_role_name,
                             article_table_name=article_table_name, term_table_name=term_table_name,
                             log_group_name=log_group_name, lambda_main_function_name=lambda_main_function_name,
                             lambda_batch_function_name=lambda_batch_function_name, lambda_layer_name=lambda_layer_name,
                             main_scheduler_name=main_scheduler_name, batch_scheduler_name=batch_scheduler_name)

def get_resource_ids_names(is_dev: bool = False):
    if is_dev:
        return ResourceIds.get_resource_dev_ids(), ResourceNames.get_resource_dev_names()
    else:
        return ResourceIds.get_resource_ids(), ResourceNames.get_resource_names()
