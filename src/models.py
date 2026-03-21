from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
import re

class InstanceInfo(BaseModel):
    instance_id: str = Field(..., min_length=1, max_length=30)
    instance_type: str = Field(..., min_length=1, max_length=30)
    state: str = Field(..., min_length=1, max_length=30)
    public_ip: str | None = Field(default=None)
    private_ip: str = Field(min_length=1, max_length=30)
    launch_time: datetime
    name: str | None = Field(default=None)
    tags: dict[str, str] = Field(..., min_length=1, max_length=50)

    @field_validator("instance_id")
    @classmethod
    def instance_id_validation(cls, instance_id: str) -> str:
        match = re.match(r'^i-[0-9a-f]+$', instance_id)
        if not match:
            raise ValueError("The instance id provided is invalid!")
        return instance_id

    @field_validator("state")
    @classmethod
    def state_validator(cls, state: str) -> str:
        valid_states = ["pending", "running", "shutting-down", "terminated", "stopping", "stopped"]
        if state not in valid_states:
            raise ValueError("State provided is invalid!")
        return state

    @field_validator("instance_type")
    @classmethod
    def instance_type_validator(cls, instance_type: str) -> str:
        pattern = r"^[a-z][a-z0-9]*\d[a-z]*\.(nano|micro|small|medium|x?large|\d+xlarge|metal)$"
        if not re.match(pattern, instance_type):
            raise ValueError(f"Invalid instance type format: {instance_type}")
        return instance_type

class SecurityGroupInfo(BaseModel):
    group_id: str = Field(..., min_length=1, max_length=100)
    group_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=100)
    vpc_id: str = Field(..., min_length=1, max_length=100)
    ingress_rule: list[dict] = Field(...,max_length=100)
    egress_rule: list[dict] = Field(...,max_length=100)

class VolumeInfo(BaseModel):
    volume_id: str = Field(..., min_length=1, max_length=100)
    size_gib: int = Field(..., gt=0, le=16384)
    volume_type: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    availability_zone: str = Field(..., min_length=1, max_length=100)
    attached_instance_id: str | None = Field(default=None)
    device: str | None = Field(default=None)

    @field_validator("volume_type")
    @classmethod
    def volume_type_validator(cls, type: str) -> str:
        allowed_types = ["gp3", "gp2", "io1", "st1", "sc1"]
        if type not in allowed_types:
            raise ValueError("Volume type not allowed!")
        return type

class CPUMetric(BaseModel):
    instance_id: str = Field(..., min_length=1, max_length=100)
    average_cpu: float = Field(...)
    max_cpu: float = Field(...)
    period_hours: int = Field(..., gt=0)
    data_points: int = Field(..., ge=0)

    @field_validator("average_cpu", "max_cpu")
    @classmethod
    def cpu_range_validator(cls, value: float) -> float:
        if not (0.0 <= value <= 100.0):
            raise ValueError("CPU value must be between 0.0 and 100.0")
        return value

class CostEntry(BaseModel):
    service: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(...)
    currency: str = Field(default="USD", min_length=1, max_length=10)
    start_date: date = Field(...)
    end_date: date = Field(...)

    @field_validator("amount")
    @classmethod
    def amount_validator(cls, amount: float):
        if amount < 0:
            raise ValueError("Amount must be a positive value!")
        return amount


