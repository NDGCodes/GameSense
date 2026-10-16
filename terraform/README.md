# GameSense Terraform

This directory defines the AWS foundation for the GameSense infrastructure walkthrough:

- VPC with public subnets for load balancers and private subnets for worker nodes.
- Single NAT gateway for private-node egress in a cost-conscious demo layout.
- EKS 1.30 cluster with managed node group, IRSA, and core EKS add-ons.

No Terraform command in this repository should be treated as evidence of live AWS resources unless it is run against an authorized AWS account and the resulting plan/apply output is captured.

## Local validation without provisioning

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

These commands download providers/modules but do not create cloud resources.

## Authorized provisioning flow

```bash
terraform plan -out gamesense.plan
# Review the plan, estimated cost, region, and account before applying.
terraform apply gamesense.plan
aws eks update-kubeconfig --region <region> --name <cluster_name>
```

Apply only after explicit authorization to create billable AWS resources. Configure AWS credentials outside the repository and never commit state files, plan files, credentials, kubeconfigs, or screenshots containing secrets.
