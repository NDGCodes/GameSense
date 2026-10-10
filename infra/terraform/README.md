# GameSense Terraform

This starter creates an AWS VPC with two public subnets and an EKS managed node group for the M10 demo. It is not applied by this repository scaffold.

```bash
terraform init
terraform plan -out gamesense.plan
# Apply only when ready to create billable AWS resources:
# terraform apply gamesense.plan
```

Replace defaults as needed, configure AWS credentials externally, and capture real plan/apply output for the submission evidence.
