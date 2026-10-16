variable "aws_region" {
  description = "AWS region for the GameSense EKS foundation."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "gamesense-m10"
}

variable "environment" {
  description = "Environment tag applied to AWS resources."
  type        = string
  default     = "demo"
}

variable "vpc_cidr" {
  description = "CIDR block for the GameSense VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDR blocks used for internet-facing load balancers."
  type        = list(string)
  default     = ["10.42.1.0/24", "10.42.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDR blocks used for EKS managed node groups."
  type        = list(string)
  default     = ["10.42.11.0/24", "10.42.12.0/24"]
}

variable "node_instance_types" {
  description = "Instance types for the default EKS managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 3
}

variable "node_desired_size" {
  description = "Desired number of worker nodes."
  type        = number
  default     = 2
}
