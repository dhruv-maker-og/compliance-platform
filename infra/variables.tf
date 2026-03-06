variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus2"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

variable "project_name" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "compliance"
}

variable "github_token" {
  description = "GitHub personal access token for Copilot SDK"
  type        = string
  sensitive   = true
}

variable "allowed_origins" {
  description = "CORS allowed origins for the API"
  type        = list(string)
  default     = ["https://compliance.example.com"]
}

variable "container_image_tag" {
  description = "Container image tag to deploy"
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  description = "CPU allocation for backend container"
  type        = number
  default     = 1.0
}

variable "backend_memory" {
  description = "Memory allocation (Gi) for backend container"
  type        = string
  default     = "2Gi"
}

variable "min_replicas" {
  description = "Minimum number of backend replicas"
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "Maximum number of backend replicas"
  type        = number
  default     = 5
}
