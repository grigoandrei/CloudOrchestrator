import typer
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from src.errors import format_aws_error, format_credentials_error, retry_on_throttle
from src.models import CostEntry
from datetime import datetime, timedelta

cost_app = typer.Typer()

@cost_app.command("report")
@retry_on_throttle(max_retries=3)
def generate_report(
    days: int = typer.Option(30, help="Number of days to look back"),
) -> None:
    ce = boto3.client("ce")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        response = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Elastic Compute Cloud - Compute"],
                }
            },
            GroupBy=[{"Type": "DIMENSION", "Key": "INSTANCE_TYPE"}],
        )
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {}))
        raise typer.Exit(1)

    for result in response["ResultsByTime"]:
        for group in result["Groups"]:
            entry = CostEntry(
                service=group["Keys"][0],
                amount=float(group["Metrics"]["UnblendedCost"]["Amount"]),
                currency=group["Metrics"]["UnblendedCost"]["Unit"],
                start_date=result["TimePeriod"]["Start"],
                end_date=result["TimePeriod"]["End"],
            )
            typer.echo(
                f"{entry.service}  ${entry.amount:.2f} {entry.currency}  "
                f"{entry.start_date} → {entry.end_date}"
            )

@cost_app.command("summary")
@retry_on_throttle(max_retries=3)
def cost_summary(
    days: int = typer.Option(7, help="Number of days to look back"),
) -> None:
    ce = boto3.client("ce")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        response = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Elastic Compute Cloud - Compute"],
                }
            },
            GroupBy=[{"Type": "DIMENSION", "Key": "INSTANCE_TYPE"}],
        )
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {}))
        raise typer.Exit(1)
    
    totals: dict[str, float] = {}
    for result in response["ResultsByTime"]:
        for group in result["Groups"]:
            instance_type = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            totals[instance_type] = totals.get(instance_type, 0.0) + amount
    
    typer.echo(f"EC2 Cost Summary (last {days} days)")
    typer.echo("-" * 40)
    grand_total = 0.0
    for instance_type, amount in sorted(totals.items()):
        typer.echo(f"{instance_type:20s}  ${amount:.2f}")
        grand_total += amount
    typer.echo("-" * 40)
    typer.echo(f"{'Total':20s}  ${grand_total:.2f}")
