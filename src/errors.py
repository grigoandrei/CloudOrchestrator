from botocore.exceptions import ClientError
import time
import functools

def format_aws_error(error: ClientError, context: dict | None) -> str:
    code = error["Error"]["Code"]

    if code == "InvalidAMIID.NotFound":
        ami_id = context.get("ami_id", "unknown")
        region = context.get("region", "unknown")
        return f"AMI {ami_id} not found in region {region}. Verify the AMI ID and region."

    if code == "UnauthorizedOperation":
        message = error.response["Error"].get("Message", "")
        return f"Insufficient permissions. {message}"
    
    if code == "RequestLimitExceeded":
        return "AWS API rate limit reached. Please wait and try again."
    
    return f"AWS error ({code}): {error.response['Error'].get('Message', 'Unknown error')}"


def format_credentials_error() -> str:
    return (
        "AWS credentials not found. Configure credentials using "
        "`aws configure` or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
        "environment variables."
    )

def retry_on_throttle(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except ClientError as e:
                    if e.response["Error"]["Code"] != "RequestLimitExceeded":
                        raise  # not a throttle error, don't retry
                    if attempt == max_retries:
                        raise  # exhausted retries
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
        return wrapper
    return decorator
