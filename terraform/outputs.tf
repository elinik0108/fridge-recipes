output "api_function_url" {
  description = "Public URL for the API"
  value = aws_lambda_function_url.api.function_url
}

output "frontend_url" {
  description = "Public URL for the frontend"
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}

output "uploads_bucket" {
  value = aws_s3_bucket.uploads.id
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.id
}

output "inference_ecr_url" {
  value = aws_ecr_repository.inference.repository_url
}

output "api_ecr_url" {
  value = aws_ecr_repository.api.repository_url
}

output "dynamodb_table" {
  value = aws_dynamodb_table.scans.name
}