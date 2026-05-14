#!/usr/bin/env bash
set -euo pipefail

: "${AWS_ACCOUNT:?Need AWS_ACCOUNT exported}"
: "${AWS_REGION:?Need AWS_REGION exported}"
DIST_ID="${DIST_ID:?Need DIST_ID exported}"

npm run build

aws s3 sync dist/ s3://fridge-frontend-${AWS_ACCOUNT}/ --delete

aws cloudfront create-invalidation \
  --distribution-id ${DIST_ID} \
  --paths "/*" \
  --query 'Invalidation.Id' --output text

echo "Deployed. CloudFront invalidation in progress (~1 min)."