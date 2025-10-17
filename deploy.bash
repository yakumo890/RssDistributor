#!/bin/bash

deploy_user=yakumo_dev
s3_bucket_name=rss-distributor-bucket 

if [ "$rss_distributor_env" == "dev" ]; then
  layer_name=RssDistributorLayerDev
  function_name=RssDistributorDev
  config_dir=./lambda/config_dev
  env_file=env_dev.json
  s3_dir=config_dev
else
  layer_name=RssDistributorLayer
  function_name=RssDistributor
  config_dir=./lambda/config
  env_file=env.json
  s3_dir=config
fi

if [ ! -d ./python ]; then
  mkdir python
fi
cp -r ./lambda/.venv/lib/python3.12/site-packages/* python/ && zip -r python.zip python/

layer_version=\
`aws-vault exec $deploy_user -- \
  aws lambda publish-layer-version \
  --layer-name $layer_name \
  --zip-file fileb://python.zip \
  --compatible-runtimes python3.12 | 
  xargs -I {} echo {} | grep LayerVersionArn | awk -F' ' '{print $2}' | sed s/,//g`

cd ./lambda
zip -r ../lambda_function.zip lambda_function.py src/*.py
cd ..

aws-vault exec $deploy_user -- \
  aws lambda update-function-configuration \
  --function-name $function_name \
  --layers $layer_version \
  --environment file://lambda/$env_file \
  > /dev/null 

sleep 5 # "An update is in progress for resource."のエラーでupdate-function-codeが失敗する場合があるのでスリープ

aws-vault exec $deploy_user -- \
  aws lambda update-function-code \
  --function-name $function_name \
  --zip-file fileb://lambda_function.zip \
  > /dev/null

rm -rf python python.zip lambda_function.zip

aws-vault exec $deploy_user -- aws s3 sync $config_dir s3://$s3_bucket_name/$s3_dir 