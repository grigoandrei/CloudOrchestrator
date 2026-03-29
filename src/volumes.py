import typer
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from src.models import VolumeInfo
from src.errors import format_aws_error, format_credentials_error

volume_app = typer.Typer()

def _parse_volumes(vol: dict) -> VolumeInfo:
    attachments = vol.get("Attachments", [])
    return VolumeInfo(
        volume_id=vol["VolumeId"],
        size_gib=vol["Size"],
        volume_type=vol["VolumeType"],
        state=vol["State"],
        availability_zone=vol["AvailabilityZone"],
        attached_instance_id=attachments[0]["InstanceId"] if attachments else None,
        device=attachments[0]["Device"] if attachments else None,
    )

@volume_app.command("create")
def create_volume(
    size: int = typer.Option(..., help="Volume size in GiB"),
    availability_zone: str = typer.Option(..., help="AZ, e.g. us-east-1a"),
    volume_type: str = typer.Option("gp3", help="Volume type: gp3, gp2, io1, st1, sc1"),
    iops: Optional[int] = typer.Option(None, help="IOPS (required for io1)"),
) -> None:
    client = boto3.client("ec2")
    if volume_type == "io1" and iops is None:
        typer.echo("Error: --iops is required for io1 volume type")
        raise typer.Exit(1)
    params = {
        "Size": size,
        "AvailabilityZone": availability_zone,
        "VolumeType": volume_type
    }
    if iops is not None:
        params["Iops"] = iops
    try:
        response = client.create_volume(**params)
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"volume_type": volume_type, "az": availability_zone}))
        raise typer.Exit(1)
    typer.echo(f'Created volume: {response["VolumeId"]} ({response["Size"]} GiB) in {response["AvailabilityZone"]}')

@volume_app.command("attach")
def attach_volume(
    volume_id: str = typer.Argument(..., help="Volume ID"),
    instance_id: str = typer.Option(..., help="Instance ID to attach to"),
    device: str = typer.Option("/dev/sdf", help="Device name"),
    dry_run: bool = typer.Option(False, help="Preview without attaching"),
) -> None:
    client = boto3.client("ec2")

    try:
        # Check AZ match before attaching
        vol_response = client.describe_volumes(VolumeIds=[volume_id])
        vol_az = vol_response["Volumes"][0]["AvailabilityZone"]

        inst_response = client.describe_instances(InstanceIds=[instance_id])
        inst_az = inst_response["Reservations"][0]["Instances"][0]["Placement"]["AvailabilityZone"]

        if vol_az != inst_az:
            typer.echo(
                f"Error: Volume {volume_id} is in {vol_az} but instance {instance_id} is in {inst_az}. "
                "Volumes can only be attached to instances in the same AZ."
            )
            raise typer.Exit(1)

        params = {
            "VolumeId": volume_id,
            "InstanceId": instance_id,
            "Device": device,
            "DryRun": dry_run,
        }
        response = client.attach_volume(**params)
        typer.echo(f'Attached volume {response["VolumeId"]} to instance {response["InstanceId"]}')
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"volume_id": volume_id, "instance_id": instance_id}))
        raise typer.Exit(1)

@volume_app.command("list")
def list_volumes() -> None:
    client = boto3.client("ec2")
    try:
        response = client.describe_volumes()
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e))
        raise typer.Exit(1)

    for vol_data in response["Volumes"]:
        vol = _parse_volumes(vol_data)
        typer.echo(
            f"\n{vol.volume_id}  {vol.size_gib} GiB  {vol.volume_type}  "
            f"{vol.state}  {vol.availability_zone}  "
            f"attached: {vol.attached_instance_id or 'none'}"
        )
    




    