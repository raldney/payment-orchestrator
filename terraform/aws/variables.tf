variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-2"
}

variable "instance_type" {
  description = "EC2 instance type (t3.medium recommended for 4GB RAM)"
  type        = string
  default     = "t3.medium"
}

variable "project_name" {
  description = "Project name tag"
  type        = string
  default     = "payment-orchestrator"
}
