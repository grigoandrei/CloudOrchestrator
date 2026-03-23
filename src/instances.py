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