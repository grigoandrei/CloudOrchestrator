import typer
import boto3
from typing import Optional

from src.instances import instances_app
from src.security_groups import sg_app
from src.volumes import volume_app
from src.tags import tags_app
from src.monitor import monitor_app
from src.cost import cost_app

app = typer.Typer(help="CloudOrchestrator - AWS EC2 management CLI")

app.add_typer(instances_app, name="instances", help="Manage EC2 instances")
app.add_typer(sg_app, name="sg", help="Manage security groups")
app.add_typer(volume_app, name="volumes", help="Manage EBS volumes")
app.add_typer(tags_app, name="tags", help="Manage resource tags")
app.add_typer(monitor_app, name="monitor", help="Monitor and stop idle instances")
app.add_typer(cost_app, name="cost", help="Generate cost reports")

@app.callback()
def main(
    region: Optional[str] = typer.Option(None, "--region", help="AWS region"),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile"),
):
    if region or profile:
        boto3.setup_default_session(region_name=region, profile_name=profile)

if __name__ == "__main__":
    app()