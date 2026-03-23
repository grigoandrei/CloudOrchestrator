import typer
from typing import Optional
import boto3
from src.errors import retry_on_throttle

instances_app = typer.Typer()
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
    client = boto3.client('ec2')
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

    # Tag instances with Name if provided
    if name:
        instance_ids = [inst["InstanceId"] for inst in response["Instances"]]
        client.create_tags(
            Resources=instance_ids,
            Tags=[{"Key": "Name", "Value": name}]
        )

    # Display results
    for inst in response["Instances"]:
        typer.echo(f"Launched: {inst['InstanceId']} ({inst['InstanceType']})")

@instances_app.command("list")
def list_instances(
    state: Optional[str] = typer.Option(None, help="Filter by state: running, stopped, etc."),
) -> None: 
    ec2 = boto3.resource('ec2')
    if state:
        filters = [{"Name": "instance-state-name", "Values": [state]}]
        instances = ec2.instances.filter(Filters=filters)
    else:
        instances = ec2.instances.all()
    
    for instance in instances:
        name_tag = ""
        if instance.tags:
            name_tag = next((t["Value"] for t in instance.tags if t["Key"] == "Name"), "")
        typer.echo(
            f"{instance.id}  {instance.instance_type}  {instance.state['Name']}  "
            f"{instance.public_ip_address or '-'}  {instance.private_ip_address or '-'}  {name_tag}"
        )


