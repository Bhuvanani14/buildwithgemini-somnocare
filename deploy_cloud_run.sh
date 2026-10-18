#!/usr/bin/env bash
# Deploy SomnoCare Unified CPAP, OSA Risk & Lifestyle Companion to Google Cloud Run
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
SERVICE_NAME="somnocare"

echo "Deploying ${SERVICE_NAME} to Cloud Run in project ${PROJECT_ID} (${REGION})..."

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global"

echo "Deployment complete!"
