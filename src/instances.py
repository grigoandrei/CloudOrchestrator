import typer
from typing import Optional
import boto3
from src.errors import retry_on_throttle
from src.models import InstanceInfo

instances_app = typer.Typer()


def _parse_instance(inst: dict, tags: list[dict] | None = None) -> InstanceInfo:
    """Build an InstanceInfo from a boto3 instance dict."""
    raw_tags = tags or inst.get("Tags") or []
    tag_dict = {t["Key"]: t["Value"] for t in raw_tags}
    return InstanceInfo(
        instance_id=inst["InstanceId"],
        instance_type=inst["InstanceType"],
        state=inst["State"]["Name"],
        public_ip=inst.get("PublicIpAddress"),
        private_ip=inst.get("PrivateIpAddress", ""),
        launch_time=inst["LaunchTime"],
        name=tag_dict.get("Name"),
        tags=tag_dict,
    )


@instances_app.command("create")
@retry_on_throttle(max_retries=3)
def create_instance(
    ami: str = typer.Option(..., help="AMI ID to launch"),
    instance_type: str = typer.Option("t2.micro", help="Instance type"),
    key_name: Optional[str] = typer.Option(None, help="SSH key pair name"),
    security_group_id: Optional[str] = typer.Option(None, help="Security group ID"),
    name: Optional[str] = typer.Option(None, help="Name tag for the instance"),
    count: int = typer.Option(1, help="Number of instances to launch"),
) -> None:
    client = boto3.client("ec2")
    params = {
        "ImageId": ami,
        "InstanceType": instance_type,
        "MinCount": count,
        "MaxCount": count,
    }
    if key_name:
        params["KeyName"] = key_name
    if security_group_id:
        params["SecurityGroupIds"] = [security_group_id]

    response = client.run_instances(**params)

    if name:
        instance_ids = [inst["InstanceId"] for inst in response["Instances"]]
        client.create_tags(
            Resources=instance_ids,
            Tags=[{"Key": "Name", "Value": name}],
        )
        # Inject the Name tag into each instance dict so _parse_instance sees it
        for inst in response["Instances"]:
            inst.setdefault("Tags", [])
            inst["Tags"].append({"Key": "Name", "Value": name})

    for inst in response["Instances"]:
        info = _parse_instance(inst)
        typer.echo(f"Launched: {info.instance_id} ({info.instance_type})")


@instances_app.command("list")
def list_instances(
    state: Optional[str] = typer.Option(None, help="Filter by state: running, stopped, etc."),
) -> None:
    client = boto3.client("ec2")
    filters = []
    if state:
        filters.append({"Name": "instance-state-name", "Values": [state]})

    paginator = client.get_paginator("describe_instances")
    for page in paginator.paginate(Filters=filters):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                info = _parse_instance(inst)
                typer.echo(
                    f"{info.instance_id}  {info.instance_type}  {info.state}  "
                    f"{info.public_ip or '-'}  {info.private_ip or '-'}  {info.name or ''}"
                )


@instances_app.command("terminate")
def terminate_instance(
    instance_id: str = typer.Argument(..., help="Instance ID to terminate"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    # Validate the ID format via the model before making any API call
    InstanceInfo.model_fields["instance_id"]  # ensure field exists
    import re
    if not re.match(r"^i-[0-9a-f]+$", instance_id):
        typer.echo(f"Error: '{instance_id}' is not a valid instance ID.", err=True)
        raise typer.Exit(1)

    if not force:
        confirmed = typer.confirm(f"Terminate instance {instance_id}?")
        if not confirmed:
            typer.echo("Aborted.")
            raise typer.Exit(0)

    client = boto3.client("ec2")
    response = client.terminate_instances(InstanceIds=[instance_id])
    for change in response["TerminatingInstances"]:
        typer.echo(
            f"Terminating: {change['InstanceId']} "
            f"({change['PreviousState']['Name']} → {change['CurrentState']['Name']})"
        )
