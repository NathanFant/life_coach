# Kubernetes manifests / Helm — placeholder

Kubernetes-ready deployment for the API and Celery workers (separate Deployments,
shared image), plus HPA, config from Secrets Manager (External Secrets), and
ingress. Used when we graduate from ECS Fargate to EKS (docs/DESIGN.md §16).
