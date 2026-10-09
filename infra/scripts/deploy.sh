#!/bin/bash
# Deploy to AWS ECS

set -euo pipefail

AWS_REGION=${AWS_REGION:-"us-east-1"}
ECR_REPO=${ECR_REPO:-"ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-bot-ecosystem"}
ECS_CLUSTER=${ECS_CLUSTER:-"ai-bot-cluster"}
ECS_SERVICE=${ECS_SERVICE:-"ai-bot-api"}
IMAGE_TAG=${1:-"latest"}

echo "==> Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REPO

echo "==> Building Docker image..."
docker build -t ai-bot-ecosystem:$IMAGE_TAG -f infra/docker/Dockerfile .

echo "==> Tagging and pushing..."
docker tag ai-bot-ecosystem:$IMAGE_TAG $ECR_REPO:$IMAGE_TAG
docker push $ECR_REPO:$IMAGE_TAG

echo "==> Updating ECS service..."
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION

echo "==> Waiting for deployment to stabilize..."
aws ecs wait services-stable \
    --cluster $ECS_CLUSTER \
    --services $ECS_SERVICE \
    --region $AWS_REGION

echo "✅ Deployment complete!"
