# Pulsar Cube Cost Estimation

This document estimates the runtime cost of the Pulsar Cube evaluation setup.

Snowflake and LLM costs are listed as session notes when available. The AWS H24 estimate below
excludes Snowflake compute/storage and LLM inference unless explicitly stated.

## Session Cost Notes

- **Cout LLM**: 2,45€ - seule l'inférence - toutes les questions posées à la suite dans le même contexte
- **Cout Requete Snowflake**: requêtes, insignifiant (système de cache côté cube-core). On compte le temps warehouse de la session ~10 minutes 1/6 crédit ($3/crédit) -> ~0.50 €
- **Cout Infra 'H24'**: ~$126/mois, voir l'estimation AWS ci-dessous. Hors Snowflake et hors cout LLM.

## AWS Runtime Cost Estimate

### Hypotheses

- Region: AWS Paris (`eu-west-3`).
- Pricing: public AWS on-demand pricing, USD, before tax, no reserved/savings plan discount.
- Month: 730 hours.
- Runtime: Linux/x86 ECS Fargate.
- `pulsar-ui`: 1 ECS service running H24, `0.5 vCPU / 2 GB`.
- `cube-core`: 1 ECS service running H24, `0.5 vCPU / 2 GB`.
- Production-small network pattern: private ECS tasks, one NAT Gateway.
- Application workload is kept in one AZ to limit NAT cost.
- The public ALB still needs two public subnets in two AZs because AWS Application Load Balancers
  require at least two AZ subnets.
- Snowflake compute/storage and LLM inference are excluded.
- Traffic is assumed low.
- CloudWatch Logs retention is 30 days, with 1 GB/month ingest and 1 GB stored.
- Secrets Manager stores 4 secrets for runtime credentials/configuration.
- ECR stores 2 GB of container images.

### Simple Production-Small Stack

This is an **application single-AZ** setup with the minimum public ALB footprint required by AWS:

- `pulsar-ui`, `cube-core`, and the NAT Gateway run in one primary AZ.
- The public ALB is still attached to two public subnets in two AZs because AWS requires an
  internet-facing Application Load Balancer to span at least two AZ subnets.
- The second public subnet is used for the ALB requirement only. It does not make the application
  tier highly available.

- **VPC**
  - 2 public subnets across 2 Availability Zones for the public ALB.
  - 1 private application subnet in the primary AZ for `pulsar-ui` and `cube-core`.
  - Internet Gateway.
  - 1 NAT Gateway in the primary public subnet.
  - Security groups:
    - ALB accepts HTTPS from users.
    - `pulsar-ui` accepts traffic only from the ALB.
    - `cube-core` accepts traffic only from `pulsar-ui`.

- **ECS Fargate**
  - ECS cluster.
  - `pulsar-ui` service, desired count `1`, task size `0.5 vCPU / 2 GB`.
  - `cube-core` service, desired count `1`, task size `0.5 vCPU / 2 GB`.
  - Tasks run in the private application subnet with no public IPv4 addresses.
  - Outbound traffic to OpenRouter, Snowflake public endpoints, package repositories, or external
    APIs goes through the NAT Gateway.
  - Snowflake connectivity is assumed to use public Snowflake endpoints via NAT egress, not private
    connectivity.
  - Inbound traffic goes only through the ALB and security groups.

- **Ingress**
  - 1 public Application Load Balancer.
  - HTTPS listener with ACM certificate.
  - Target group to `pulsar-ui`.
  - Optional path-based route to `cube-core` should stay disabled unless a direct Cube API endpoint
    is required.

- **Images and configuration**
  - ECR repositories for `pulsar-ui` and `cube-core` images.
  - AWS Secrets Manager for runtime secrets:
    - `OPENROUTER_API_KEY`
    - Cube API token or signing secret, depending on final packaging
    - Cube SQL password
    - Snowflake credential
  - Secret reads happen at service startup; API request cost is expected to be negligible.
  - Optional rotation Lambda cost is also expected to be negligible at this scale.

- **Observability**
  - CloudWatch Log Groups for both ECS services.
  - 30-day retention.
  - Basic ECS/ALB CloudWatch metrics.

### Monthly Cost

| Component | Assumption | Unit price | Monthly cost |
|---|---:|---:|---:|
| Fargate `pulsar-ui` | `0.5 vCPU / 2 GB` x 730h | `$0.0349/h` | `$25.48` |
| Fargate `cube-core` | `0.5 vCPU / 2 GB` x 730h | `$0.0349/h` | `$25.48` |
| Application Load Balancer | 1 ALB x 730h | `$0.02646/h` | `$19.32` |
| ALB capacity units | Low traffic estimate, 1 LCU x 730h | `$0.0084/LCU-h` | `$6.13` |
| NAT Gateway | 1 NAT Gateway x 730h | `$0.05/h` | `$36.50` |
| NAT data processing | Placeholder for outbound traffic, 1 GB/month | `$0.05/GB` | `$0.05` |
| Public IPv4 addresses | 3 IPs x 730h: 2 ALB + 1 NAT Gateway EIP | `$0.005/IP-h` | `$10.95` |
| CloudWatch Logs | 1 GB ingest + 1 GB stored/month | `$0.5985/GB ingest`, `$0.0315/GB-mo` | `$0.63` |
| Secrets Manager | 4 secrets | `$0.40/secret-mo` | `$1.60` |
| Secrets Manager API calls / rotation Lambda | Low-volume startup reads and optional rotation | negligible | `$0.00` |
| ECR storage | 2 GB stored images | `$0.10/GB-mo` | `$0.20` |
| ECS cluster, VPC, subnets, route tables, Internet Gateway, security groups | No direct hourly charge | `$0` | `$0.00` |

**Estimated AWS H24 total:** `$126.33/month`.

Rounded practical estimate: **~$125-130/month**, excluding Snowflake, LLM, data transfer, domain,
taxes, and support plan.

### Cost Notes

- The two Fargate services are roughly `$50.96/month` together.
- The NAT Gateway adds about `$36.50/month` fixed cost before data processing.
- Snowflake egress through NAT is included structurally: the NAT Gateway hourly cost is included,
  and NAT data processing is included as a 1 GB/month placeholder. Increase this line if query
  result traffic from Snowflake to Cube is materially higher.
- Secrets Manager is included for 4 secrets. API calls and rotation Lambda do not materially change
  the global monthly cost at this scale.
- The always-on ALB plus LCU assumption adds about `$25.45/month`.
- Public IPv4 charges are lower than in the public-task variant because ECS tasks no longer have
  public IPv4 addresses, but the ALB and NAT Gateway still consume public IPv4.
- This is not a fully high-availability network design: the NAT Gateway and ECS tasks are in one
  AZ. A stricter multi-AZ production setup would usually add at least a second private subnet and a
  second NAT Gateway, increasing fixed cost.
- If `cube-core` can scale to zero outside evaluation windows, its Fargate and public IPv4 cost can
  drop from about `$25.48/month` to only the minutes actually used.
- If both services scale to zero and the ALB is also torn down outside sessions, the H24 fixed cost
  can be reduced significantly, but the setup becomes an on-demand environment rather than an
  always-on service.

### Pricing Sources

- AWS Price List API, `AmazonECS`, region `eu-west-3`, checked 2026-05-29:
  Fargate Linux/x86 `vCPU = $0.0486/vCPU-h`, `memory = $0.0053/GB-h`.
- AWS Price List API, `AmazonEC2`, region `eu-west-3`, checked 2026-05-29:
  Application Load Balancer `$0.02646/h`, ALB LCU `$0.0084/LCU-h`, NAT Gateway `$0.05/h`,
  NAT Gateway data processing `$0.05/GB`.
- AWS Price List API, `AmazonVPC`, region `eu-west-3`, checked 2026-05-29:
  public IPv4 `$0.005/IP-h`.
- AWS Price List API, `AmazonCloudWatch`, region `eu-west-3`, checked 2026-05-29:
  logs ingest `$0.5985/GB`, log storage `$0.0315/GB-mo`.
- AWS Price List API, `AWSSecretsManager`, region `eu-west-3`, checked 2026-05-29:
  secret storage `$0.40/secret-mo`, API requests `$0.05/10,000 requests`.
- AWS Price List API, `AmazonECR`, region `eu-west-3`, checked 2026-05-29:
  image storage `$0.10/GB-mo`.
