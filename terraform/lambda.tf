# Shared trust policy for Lambda
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}


resource "aws_ecr_repository" "inference" {
  name = "${var.project_prefix}-inference"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_iam_role" "inference" {
  name = "${var.project_prefix}-inference-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "inference_basic" {
  role = aws_iam_role.inference.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "inference_permissions" {
  statement {
    actions = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
  statement {
    actions = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.scans.arn]
  }
}

resource "aws_iam_role_policy" "inference" {
  name = "${var.project_prefix}-inference-permissions"
  role = aws_iam_role.inference.id
  policy = data.aws_iam_policy_document.inference_permissions.json
}

resource "aws_lambda_function" "inference" {
  function_name = "${var.project_prefix}-inference"
  package_type = "Image"
  image_uri = "${aws_ecr_repository.inference.repository_url}:latest"
  role = aws_iam_role.inference.arn
  timeout = 60
  memory_size = 1024
  architectures = ["x86_64"]

  # The image URI references :latest which we'll push out-of-band.
  # Without this, future Terraform runs would detect tag updates and try to "fix" them.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

# S3 → inference Lambda wiring
resource "aws_lambda_permission" "inference_s3" {
  statement_id  = "AllowS3Invoke"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.inference.function_name
  principal = "s3.amazonaws.com"
  source_arn = aws_s3_bucket.uploads.arn
}

resource "aws_s3_bucket_notification" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.inference.arn
    events = ["s3:ObjectCreated:*"]
    filter_prefix = "uploads/"
  }

  depends_on = [aws_lambda_permission.inference_s3]
}

# ========== API Lambda ==========

resource "aws_ecr_repository" "api" {
  name = "${var.project_prefix}-api"
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_iam_role" "api" {
  name = "${var.project_prefix}-api-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "api_basic" {
  role = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "api_permissions" {
  statement {
    actions = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.uploads.arn}/*"]
  }
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.scans.arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name = "${var.project_prefix}-api-permissions"
  role = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_permissions.json
}

resource "aws_lambda_function" "api" {
  function_name = "${var.project_prefix}-api"
  package_type = "Image"
  image_uri  = "${aws_ecr_repository.api.repository_url}:latest"
  role = aws_iam_role.api.arn
  timeout = 60
  memory_size = 1024
  architectures = ["x86_64"]

  environment {
    variables = {
      GEMINI_API_KEY = var.gemini_api_key
      UPLOAD_BUCKET = aws_s3_bucket.uploads.id
      DYNAMO_TABLE = aws_dynamodb_table.scans.name
      AWS_LWA_ASYNC_INIT = "true"
    }
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_function_url" "api" {
  function_name = aws_lambda_function.api.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = ["*"]
    allow_methods = ["*"]
    allow_headers = ["*"]
  }
}

# Two permissions required for public Function URL invocation
resource "aws_lambda_permission" "api_url" {
  statement_id = "FunctionURLAllowPublicAccess"
  action  = "lambda:InvokeFunctionUrl"
  function_name = aws_lambda_function.api.function_name
  principal = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "api_invoke" {
  statement_id = "FunctionURLAllowPublicInvokeFunction"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal = "*"
}