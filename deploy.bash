#!/bin/bash

deploy_user=yakumo_dev
s3_bucket_name=rss-distributor-bucket 

if [ "$rss_distributor_env" == "dev" ]; then
  layer_name=RssDistributorLayerDev
  main_function_name=RssDistributorDev
  batch_function_name=RssDistributorBatchDev
  config_dir=./lambda/config/dev/
  main_env_file_path=lambda/main/env_dev.json
  batch_env_file_path=lambda/batch/env_dev.json
  s3_dir=config_dev
else
  layer_name=RssDistributorLayer
  main_function_name=RssDistributor
  batch_function_name=RssDistributorBatch
  config_dir=./lambda/config/prod/
  main_env_file_path=lambda/main/env.json
  batch_env_file_path=lambda/batch/env.json
  s3_dir=config
fi

if [ ! -d ./python ]; then
  mkdir python
fi
cp -r ./lambda/.venv/lib/python3.12/site-packages/* python/ && zip -r python.zip python/ > /dev/null

layer_version=\
`aws-vault exec $deploy_user -- \
  aws lambda publish-layer-version \
  --layer-name $layer_name \
  --zip-file fileb://python.zip \
  --compatible-runtimes python3.12 | 
  xargs -I {} echo {} | grep LayerVersionArn | awk -F' ' '{print $2}' | sed s/,//g`

pushd lambda/main > /dev/null
zip -r ../../lambda_main.zip lambda_function.py src/*.py > /dev/null
popd > /dev/null

pushd lambda/batch > /dev/null
zip -r ../../lambda_batch.zip lambda_function.py src/*.py > /dev/null
popd > /dev/null

aws-vault exec $deploy_user -- \
  aws lambda update-function-configuration \
  --function-name $main_function_name \
  --layers $layer_version \
  --environment file://$main_env_file_path \
  > /dev/null 

sleep 5 # "An update is in progress for resource."のエラーでupdate-function-codeが失敗する場合があるのでスリープ

aws-vault exec $deploy_user -- \
  aws lambda update-function-code \
  --function-name $main_function_name \
  --zip-file fileb://lambda_main.zip \
  > /dev/null

aws-vault exec $deploy_user -- \
  aws lambda update-function-configuration \
  --function-name $batch_function_name \
  --layers $layer_version \
  --environment file://$batch_env_file_path \
  > /dev/null 

sleep 5

aws-vault exec $deploy_user -- \
  aws lambda update-function-code \
  --function-name $batch_function_name \
  --zip-file fileb://lambda_batch.zip \
  > /dev/null

rm -rf python python.zip lambda_main.zip lambda_batch.zip

aws-vault exec $deploy_user -- aws s3 sync $config_dir s3://$s3_bucket_name/$s3_dir 
