# CloudOrchestrator

A command-line utility for managing AWS EC2 resources, built with Python, Typer, and Boto3. Designed as a hands-on learning tool for exploring EC2, CloudWatch, and Cost Explorer APIs.

## Features

- **Instance Management** — Create, list, and terminate EC2 instances
- **Security Groups** — Create groups and manage ingress/egress rules
- **Volume Management** — Create EBS volumes and attach/detach from instances
- **Tagging** — Apply, list, and remove tags on any EC2 resource
- **Idle Instance Detection** — Query CloudWatch CPU metrics and stop underutilized instances
- **Cost Reporting** — Generate EC2 cost breakdowns via Cost Explorer

## Prerequisites

- Python 3.10+
- AWS credentials configured (`aws configure` or environment variables)
- IAM permissions for EC2, CloudWatch, and Cost Explorer

## Installation

```bash
pip install -r requirements.txt

```

## Usage

```bash
# Instance operations
cloud-orch instances create --ami ami-0abcdef1234567890 --instance-type t2.micro --name "my-server"
cloud-orch instances list --state running
cloud-orch instances terminate i-0123456789abcdef0

# Security groups
cloud-orch sg create web-server --description "Web server SG"
cloud-orch sg add-rule sg-0123456789abcdef0 --port 22 --protocol tcp --cidr 203.0.113.0/24
cloud-orch sg list

# Volumes
cloud-orch volumes create --size 20 --availability-zone us-east-1a --volume-type gp3
cloud-orch volumes attach vol-0123456789abcdef0 --instance-id i-0123456789abcdef0
cloud-orch volumes list

# Tags
cloud-orch tags set i-0123456789abcdef0 --tags Environment=dev --tags Team=backend
cloud-orch tags list i-0123456789abcdef0
cloud-orch tags remove i-0123456789abcdef0 --keys Environment

# Monitoring
cloud-orch monitor cpu i-0123456789abcdef0 --hours 6
cloud-orch monitor stop-idle --threshold 5.0 --period-hours 24 --dry-run

# Cost reports
cloud-orch cost report --days 30
cloud-orch cost summary --days 7
```

## Project Structure

```
src/
├── main.py              # Typer app entry point
├── instances.py         # EC2 instance management
├── security_groups.py   # Security group management
├── volumes.py           # EBS volume management
├── tags.py              # Resource tagging
├── monitor.py           # CloudWatch metrics & idle detection
└── cost.py              # Cost Explorer reporting
```

## Testing

```bash
# Run unit tests (uses moto for AWS mocking)
pytest

# Run property-based tests
pytest tests/ -k "property"
```

## Dependencies

- **boto3** — AWS SDK for Python
- **typer** — CLI framework
- **rich** — Formatted terminal output (optional)
- **moto** — AWS mocking for tests (dev)
- **hypothesis** — Property-based testing (dev)
- **pytest** — Test runner (dev)
