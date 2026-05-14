Phone camera
  → CloudFront (edge HTTPS + caching)
  → S3 (React/Vite static bundle)
  → Lambda Function URL (FastAPI + boto3 + Gemini)
  → presigned PUT → S3 uploads bucket
  → S3 ObjectCreated event
  → Lambda container (ONNX YOLOv8 inference)
  → DynamoDB
  → API polling reads DynamoDB
  → Gemini call generates recipes
  → recipes shown on the phone