# Pulsar Bare Cost Estimation

This document estimates the runtime cost of the Pulsar Bare evaluation setup.

Snowflake and LLM costs are listed as session notes when available. The AWS H24 estimate below
excludes Snowflake compute/storage and LLM inference unless explicitly stated.

## Cost Recap

- **LLM cost**: ~$2.40 (estimate) — inference only, all questions asked consecutively in a single
  context, via the Anthropic API.
- **Snowflake query cost**: ~$0.50 — ~10 minutes of warehouse time (XS, 1/6 credit at ~$3/credit).
  The agent runs raw SQL directly against the gold layer, so warehouse time per session stays small
  on the XS warehouse (fast FieldOps queries).
- **'H24' infra cost**: ~$100/month, see the AWS estimate below. Excludes Snowflake and LLM costs.

## AWS Runtime Cost Estimate

### Hypotheses

- Region: AWS Paris (`eu-west-3`).
- Pricing: public AWS on-demand pricing, USD, before tax, no reserved/savings plan discount.
- Month: 730 hours.
- Runtime: Linux/x86 ECS Fargate.
- `pulsar-bare-api`: 1 ECS service running H24, `0.5 vCPU / 2 GB`. The LangGraph agent runs
  in-process; there is no separate agent service.
- `pulsar-web`: static React SPA hosted on **S3**, delivered through **CloudFront**; CloudFront
  routes `/api` to the API's ALB. No Fargate for the frontend.
- Conversation state (`pulsar_api.db`, sqlite): **ephemeral** Fargate storage, lost on task restart
  (POC). No EFS.
- Production-small network pattern: private ECS task, one NAT Gateway.
- Application workload kept in one AZ to limit NAT cost.
- The public ALB still needs two public subnets in two AZs (AWS requires an internet-facing ALB to
  span at least two AZ subnets).
- Snowflake compute/storage and LLM inference are excluded.
- Traffic is assumed low; S3 + CloudFront stay within the AWS always-free tier at POC volumes.
- CloudWatch Logs retention is 30 days, ~1 GB/month ingest and 1 GB stored.
- Secrets Manager stores 2 secrets for runtime credentials.
- ECR stores ~1 GB of container images (the single API image).

### Simple Production-Small Stack

An **application single-AZ** setup: one backend Fargate service, a static frontend on S3/CloudFront,
the minimum public ALB footprint required by AWS.

- **VPC**
  - 2 public subnets across 2 AZs for the public ALB.
  - 1 private application subnet in the primary AZ for `pulsar-bare-api`.
  - Internet Gateway; 1 NAT Gateway in the primary public subnet.
  - Security groups: ALB accepts HTTPS (from CloudFront / users); `pulsar-bare-api` accepts traffic
    only from the ALB.

- **ECS Fargate**
  - ECS cluster.
  - `pulsar-bare-api` service, desired count `1`, task size `0.5 vCPU / 2 GB`.
  - Task runs in the private subnet with no public IPv4.
  - Outbound to the Anthropic API and Snowflake public endpoints goes through the NAT Gateway.
  - Inbound only through the ALB and security groups.

- **Frontend (static)**
  - Private S3 bucket holding the built SPA (`dist/`).
  - CloudFront distribution (Origin Access Control) with an ACM certificate: default origin = S3;
    `/api/*` behavior forwards to the ALB origin.

- **Ingress**
  - 1 public Application Load Balancer, HTTPS listener with ACM certificate, target group to
    `pulsar-bare-api`.

- **Images and configuration**
  - 1 ECR repository for the `pulsar-bare-api` image.
  - AWS Secrets Manager: `ANTHROPIC_API_KEY`, Snowflake private key (non-secret Snowflake config —
    account/user/role/warehouse — can be plain task env vars).

- **Observability**
  - CloudWatch Log Group for the ECS service, 30-day retention. Basic ECS/ALB metrics.

### Monthly Cost

| Component | Assumption | Unit price | Monthly cost |
|---|---:|---:|---:|
| Fargate `pulsar-bare-api` | `0.5 vCPU / 2 GB` x 730h | `$0.0349/h` | `$25.48` |
| S3 (static SPA hosting) | < 0.1 GB stored, low requests | free tier | `$0.00` |
| CloudFront (SPA delivery) | Low traffic, within free tier | free tier | `$0.00` |
| Application Load Balancer | 1 ALB x 730h | `$0.02646/h` | `$19.32` |
| ALB capacity units | Low traffic estimate, 1 LCU x 730h | `$0.0084/LCU-h` | `$6.13` |
| NAT Gateway | 1 NAT Gateway x 730h | `$0.05/h` | `$36.50` |
| NAT data processing | Placeholder for outbound traffic, 1 GB/month | `$0.05/GB` | `$0.05` |
| Public IPv4 addresses | 3 IPs x 730h: 2 ALB + 1 NAT Gateway EIP | `$0.005/IP-h` | `$10.95` |
| CloudWatch Logs | 1 GB ingest + 1 GB stored/month | `$0.5985/GB ingest`, `$0.0315/GB-mo` | `$0.63` |
| Secrets Manager | 2 secrets | `$0.40/secret-mo` | `$0.80` |
| ECR storage | 1 GB stored image | `$0.10/GB-mo` | `$0.10` |
| ECS cluster, VPC, subnets, route tables, Internet Gateway, security groups | No direct hourly charge | `$0` | `$0.00` |

**Estimated AWS H24 total:** `$99.96/month`.

Rounded practical estimate: **~$95-100/month**, excluding Snowflake, LLM, data transfer, domain,
taxes, and support plan.

### Cost Notes

- **A single Fargate service (`$25.48`)** keeps compute cost low: the agent runs in-process in the
  API, and the frontend is static (S3/CloudFront) rather than a server-rendered app.
- The **NAT Gateway** (`$36.50`) is still the largest fixed line.
- The always-on **ALB + LCU** (`~$25.45`) is still required to reach the private API.
- **S3 + CloudFront ≈ `$0`** at POC traffic (always-free tier); this becomes a small variable cost
  only at materially higher traffic (CloudFront egress after the 1 TB free tier).
- **Public IPv4**: 3 IPs (2 ALB + 1 NAT); CloudFront does not consume our IPv4.
- **Ephemeral sqlite** is fine for evaluation; a production setup wanting persistent history would
  add EFS (small) or move state to a managed store (RDS/DynamoDB).
- **Scale-to-zero option**: if the API service and ALB are torn down outside evaluation windows, the
  H24 fixed cost drops to on-demand.

### Pricing Sources

- AWS Price List API figures (region `eu-west-3`, checked 2026-05-29):
  Fargate Linux/x86 `vCPU = $0.0486/vCPU-h`, `memory = $0.0053/GB-h`; ALB `$0.02646/h`, ALB LCU
  `$0.0084/LCU-h`, NAT Gateway `$0.05/h`, NAT data `$0.05/GB`; public IPv4 `$0.005/IP-h`; CloudWatch
  logs ingest `$0.5985/GB`, storage `$0.0315/GB-mo`; Secrets Manager `$0.40/secret-mo`; ECR
  `$0.10/GB-mo`.
- S3 static hosting and CloudFront delivery: within the AWS always-free tier at POC traffic, so
  listed as `$0.00`. Reference rates beyond the free tier (approximate, `eu-west-3`): S3 Standard
  `~$0.0245/GB-mo`, CloudFront egress `~$0.085/GB` after the first 1 TB/month.
