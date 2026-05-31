# Terraform (AWS) — placeholder

Provisions the production environment (docs/DESIGN.md §3.1, §17): VPC, RDS/Aurora
Postgres (pgvector), ElastiCache Redis, ECS Fargate (API + workers) → EKS at scale,
KMS, Secrets Manager, S3, WAF/ALB.

Added in Phase 0. Keep state in a remote backend (S3 + DynamoDB lock). No secrets in code.
