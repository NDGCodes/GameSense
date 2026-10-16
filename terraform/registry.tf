# Optional private staging registry for an ephemeral capstone deployment.
# GHCR remains the CI publishing target. Enable only for the demo lifecycle.
variable "create_demo_registry" {
  type        = bool
  description = "Create disposable private ECR repositories for deployment image staging."
  default     = false
}

resource "aws_ecr_repository" "demo" {
  for_each             = var.create_demo_registry ? toset(["backend", "frontend"]) : toset([])
  name                 = "${var.cluster_name}-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

output "demo_registry_urls" {
  value = { for service, repository in aws_ecr_repository.demo : service => repository.repository_url }
}
