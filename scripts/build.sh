#!/usr/bin/env bash
# Build and push the bookeo-sync Docker image using buildx.
# Usage: ./scripts/build.sh [tag]   (default: v1)
#
# Prerequisites: az acr login --name corkandcandlesacr (or your ACR name)

set -e

IMAGE="${IMAGE:-corkandcandlesacr.azurecr.io/bookeo-sync}"
TAG="${1:-v1}"
FULL_IMAGE="${IMAGE}:${TAG}"

echo "Building ${FULL_IMAGE} with buildx..."
docker buildx build \
  --platform linux/amd64 \
  -t "${FULL_IMAGE}" \
  --push \
  .

echo "Pushed ${FULL_IMAGE}"
