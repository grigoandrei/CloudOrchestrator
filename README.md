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

The quickest way to get started:

```bash
git clone <repo-url> && cd CloudOrchestrator
./install.sh
source ~/.zshrc  # or ~/.bashrc
```

The install script will:
- Verify Python 3.10+ is available
- Create a virtual environment and install all dependencies
- Add the `cloud-orch` command to your PATH

If you prefer to set things up manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --help
```

## Usage

You can use `cloud-orch` directly if you ran the install script, or `python -m src.main` from the project root.

```bash
# Show all available commands
cloud-orch --help

# Use a specific AWS region or profile
cloud-orch --region us-west-2 --profile dev instances list
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
# Run all tests
python -m pytest tests/ -v

# Run just the property-based tests
python -m pytest tests/ -k "test_" -v
```

## Dependencies

- **boto3** — AWS SDK for Python
- **typer** — CLI framework
- **rich** — Formatted terminal output (optional)
- **moto** — AWS mocking for tests (dev)
- **hypothesis** — Property-based testing (dev)
- **pytest** — Test runner (dev)
