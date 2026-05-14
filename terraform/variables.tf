variable "aws_region" {
  type        = string
  default     = "eu-north-1"
  description = "AWS region for all resources"
}

variable "aws_account_id" {
  type        = string
  description = "AWS account ID (used in bucket names)"
}

variable "gemini_api_key" {
  type        = string
  sensitive   = true
  description = "Gemini API key for recipe generation"
}

variable "project_prefix" {
  type        = string
  default     = "fridge"
  description = "Prefix for all resource names"
}