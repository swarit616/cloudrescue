# Architecture

## Current (implemented and runnable locally)

```mermaid
flowchart LR
    User["Developer / curl"] -->|HTTP| API
    subgraph Compose["Docker Compose (127.0.0.1 only)"]
        API["CloudRescue API (FastAPI) :8000"]
        PROM["Prometheus :9090"]
        STATE[("In-memory simulation state\n(lost on restart)")]
        API --- STATE
        PROM -->|scrape /metrics every 15s| API
    end
    API -. "no calls in this phase" .-> AWS[("AWS (not connected)")]
```

## Planned (Terraform written, never applied)

```mermaid
flowchart TB
    subgraph VPC["VPC (module: network)"]
        subgraph Public["Public subnet"]
            EC2["EC2 + Docker\n(module: compute)"]
        end
        Private["Private subnet\n(no NAT yet)"]
    end
    IAM["IAM role\nSSM + own log group only\n(module: iam)"] --> EC2
    EC2 -->|awslogs driver| CWL["CloudWatch Logs"]
    EC2 --> CWM["CloudWatch metrics + alarms\n(module: monitoring)"]
    ALB["ALB + Auto Scaling\n(deferred)"] -.-> EC2
```

## Components

| Component | Responsibility | Files |
|---|---|---|
| FastAPI app | Endpoints, validation, error format, request ids, JSON logs | `app/main.py`, `app/routes.py`, `app/models.py` |
| Simulation state | Thread-safe healthy/failed state machine and bounded incident history (standard library only) | `app/state.py` |
| Metrics | Per-app Prometheus registry; `cloudrescue_simulated_*` for the simulation, `cloudrescue_aws_*` for AWS config | `app/metrics.py` |
| Config | Environment-variable settings with safe defaults | `app/config.py` |
| Prometheus | Scrapes `cloudrescue:8000/metrics`, one alert for the simulated failure | `prometheus/` |
| Terraform | Future AWS environment definition | `terraform/` |

## Simulation versus AWS

The simulation and AWS information are separate on purpose:

* `GET /api/status` has `simulated_service` (changes with the demo endpoints) and `aws` (never changes with the simulation).
* `aws.integration_implemented` is `false` and `aws.status` is `not_checked`; `aws.configured` only reflects whether a future
  target region + instance id were described through environment variables.
* Every incident carries `simulated: true` and `source: "local-simulation"`.
* Metric names containing `simulated` can never be mistaken for real signals.

## HTTP semantics

| Situation | Response |
|---|---|
| Process alive | `GET /health` -> 200 (independent of the simulation) |
| Simulated service failed | `GET /api/status` -> 503 with the normal body |
| Failure simulated | `POST /api/demo/simulate-failure` -> 201 |
| Failure when already failed / recover when healthy | 409 |
| Invalid body or query | 422 with `details` |
| Demo endpoints disabled | 403; missing/invalid `X-Demo-Token` -> 401 |
