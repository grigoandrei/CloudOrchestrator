import typer
from typing import Optional
import boto3

sg_app = typer.Typer()

@sg_app.command('create')
def create_security_group(
    name: str = typer.Argument(..., help="Security group name"),
    description: str = typer.Option("Managed by CloudOrchestrator", help="Description"),
    vpc_id: Optional[str] = typer.Option(None, help="VPC ID (uses default VPC if omitted)"),
) -> None:
    client = boto3.client('ec2')
    params = {
        "Description": description,
        "GroupName": name,
    }
    if vpc_id:
        params["VpcId"] = vpc_id
    response = client.create_security_group(**params)

    typer.echo(f"Created: {response['GroupId']} ({name})")

@sg_app.command("add-rule")
def add_ingress_rule(
    group_id: str = typer.Argument(..., help="Security group ID"),
    from_port: int = typer.Option(..., help="Start port number"),
    to_port: Optional[int] = typer.Option(None, help="End port (defaults to from_port for single port)"),
    protocol: str = typer.Option("tcp", help="Protocol: tcp, udp, icmp"),
    cidr: str = typer.Option("0.0.0.0/0", help="CIDR block for source"),
) -> None:
    client = boto3.client('ec2')
    if to_port is None:
        to_port = from_port
    if cidr == "0.0.0.0/0":
        typer.echo("⚠️  Warning: This rule is open to the entire internet (0.0.0.0/0)")
    params = {
        "GroupId": group_id,
        "FromPort": from_port,
        "ToPort": to_port,
        "IpProtocol": protocol,
        "CidrIp": cidr,
    }

    client.authorize_security_group_ingress(**params)
    typer.echo(f"Added rule: {protocol} port {from_port}-{to_port} from {cidr} to {group_id}")

@sg_app.command("list")
def list_security_groups() -> None:
    client = boto3.client('ec2')
    response = client.describe_security_groups()

    for sg in response["SecurityGroups"]:
        typer.echo(f"\n{sg['GroupId']}  {sg['GroupName']}  VPC: {sg['VpcId']}")
        typer.echo(f"  Description: {sg['Description']}")

        # Ingress rules
        if sg["IpPermissions"]:
            typer.echo("  Inbound rules:")
            for rule in sg["IpPermissions"]:
                protocol = rule["IpProtocol"]
                from_port = rule.get("FromPort", "all")
                to_port = rule.get("ToPort", "all")
                cidrs = [r["CidrIp"] for r in rule.get("IpRanges", [])]
                typer.echo(f"    {protocol} {from_port}-{to_port} from {', '.join(cidrs) or 'N/A'}")
        else:
            typer.echo("  Inbound rules: none")

