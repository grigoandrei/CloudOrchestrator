import typer
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from src.errors import format_aws_error, format_credentials_error

tags_app = typer.Typer()

@tags_app.command("set")
def set_tags(resource_id: str = typer.Argument(..., help="Resource ID (instance, volume, SG, etc.)"),
    tags: list[str] = typer.Option(..., help="Tags as Key=Value pairs"),
) -> None:
    client = boto3.client("ec2")
    parsed_tags = []
    for tag in tags:
        if "=" not in tag:
            typer.echo(f"Error: Invalid tag format '{tag}'. Use Key=Value")
            raise typer.Exit(1)
        key, value = tag.split("=", 1)
        parsed_tags.append({"Key": key, "Value": value})

    try:
        client.create_tags(
            Resources=[resource_id],
            Tags=parsed_tags,
        )
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"tags": parsed_tags}))
        raise typer.Exit(1)
    
@tags_app.command("list")
def list_tags(
    resource_id: str = typer.Argument(..., help="Resource ID"),
) -> None:
    client = boto3.client("ec2")
    try:
        response = client.describe_tags(
            Filters=[
                {
                    'Name': 'resource-id',
                    'Values':[
                        resource_id
                    ]
                }
            ]
        )
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"resource": resource_id}))
        raise typer.Exit(1)

    if not response["Tags"]:
        typer.echo(f"No tags found for {resource_id}")
        return

    for tag in response["Tags"]:
        typer.echo(f"  {tag['Key']} = {tag['Value']}")

@tags_app.command("remove")
def remove_tags(
    resource_id: str = typer.Argument(..., help="Resource ID"),
    keys: list[str] = typer.Option(..., help="Tag keys to remove"),
) -> None:
    client = boto3.client("ec2")
    try:
        client.delete_tags(
            Resources=[resource_id],
            Tags=[{"Key": k} for k in keys],
        )
    except NoCredentialsError:
        typer.echo(format_credentials_error())
        raise typer.Exit(1)
    except ClientError as e:
        typer.echo(format_aws_error(e, {"resource": resource_id}))
        raise typer.Exit(1)

    typer.echo(f"Removed tags {', '.join(keys)} from {resource_id}")



        