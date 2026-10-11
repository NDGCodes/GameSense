output "vpc_id" {
  description = "ID of the GameSense VPC."
  value       = module.vpc.vpc_id
}

output "public_subnets" {
  description = "Public subnet IDs intended for internet-facing load balancers."
  value       = module.vpc.public_subnets
}

output "private_subnets" {
  description = "Private subnet IDs used by the EKS managed node group."
  value       = module.vpc.private_subnets
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster API endpoint."
  value       = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Command to configure kubectl after a verified terraform apply."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
