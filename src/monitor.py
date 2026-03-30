import typer
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from src.errors import format_aws_error, format_credentials_error
from datetime import datetime, timedelta
from src.models import CpuMetric

monitor_app = typer.Typer()

def get_average_cpu(instance_id: str, period_hours: int = 24) -> CpuMetric:
    cw = boto3.client("cloudwatch")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=period_hours)

    response = cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start_time,
        EndTime=end_time,
        Period=3600,  # 1-hour granularity
        Statistics=["Average", "Maximum"],
    )

    datapoints = response["Datapoints"]
    if not datapoints:
        return CpuMetric(instance_id, 0.0, 0.0, period_hours, 0)

    avg = sum(dp["Average"] for dp in datapoints) / len(datapoints)
    max_val = max(dp["Maximum"] for dp in datapoints)

    return CpuMetric(instance_id, avg, max_val, period_hours, len(datapoints))



@monitor_app.command("stop-idle")
def stop_idle_instances(
    threshold: float = typer.Option(5.0, help="CPU % below which instance is idle"),
    period_hours: int = typer.Option(24, help="Lookback period in hours"),
    dry_run: bool = typer.Option(False, help="Preview without stopping"),
) -> None:
    try:
        ec2 = boto3.resource("ec2")
        running = ec2.instances.filter(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )

        idle_ids: list[str] = []
        for instance in running:
            metric = get_average_cpu(instance.id, period_hours)
            if metric.datapoints > 0 and metric.average_cpu < threshold:
                idle_ids.append(instance.id)

        if idle_ids and not dry_run:
            ec2_client = boto3.client("ec2")
            ec2_client.stop_instances(InstanceIds=idle_ids)

        if dry_run:
            typer.echo(f"[dry-run] Would stop {len(idle_ids)} idle instance(s): {idle_ids}")
        else:
            typer.echo(f"Stopped {len(idle_ids)} idle instance(s): {idle_ids}")
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"threshold": threshold}))
        raise typer.Exit(1)

@monitor_app.command("cpu")
def show_cpu(
    instance_id: str = typer.Argument(..., help="Instance ID"),
    hours: int = typer.Option(1, help="Lookback period in hours"),
) -> None:
    try:
        metric = get_average_cpu(instance_id, hours)
        if metric.datapoints == 0:
            typer.echo("Average cpu is: 0.0% (zero datapoints)")
        else:
            typer.echo(f"Average cpu is: {metric.average_cpu:.1f}%")
            typer.echo(f"Max value for cpu is: {metric.max_cpu:.1f}%")
            typer.echo(f"Datapoints: {metric.datapoints}")
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"instance_id": instance_id}))
        raise typer.Exit(1)

