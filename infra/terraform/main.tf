provider "aws" { region = var.aws_region }

data "aws_availability_zones" "available" { state = "available" }

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.13.0"
  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets = ["10.42.1.0/24", "10.42.2.0/24"]
  enable_dns_hostnames = true
  map_public_ip_on_launch = true
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.24.0"
  cluster_name = var.cluster_name
  cluster_version = "1.30"
  subnet_ids = module.vpc.public_subnets
  vpc_id = module.vpc.vpc_id
  enable_cluster_creator_admin_permissions = true
  eks_managed_node_groups = {
    gamesense_workers = {
      instance_types = ["t3.medium"]
      min_size = 1
      max_size = 3
      desired_size = 2
    }
  }
}
