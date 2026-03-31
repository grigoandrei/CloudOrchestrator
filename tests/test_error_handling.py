from unittest.mock import patch
import pytest
from botocore.exceptions import ClientError

from src.errors import format_aws_error, format_credentials_error, retry_on_throttle


def _make_client_error(code: str, message: str = "") -> ClientError:
    """Build a botocore ClientError with the given error code."""
    error_response = {"Error": {"Code": code, "Message": message}}
    return ClientError(error_response, "TestOperation")


# ---------------------------------------------------------------------------
# format_aws_error
# ---------------------------------------------------------------------------

class TestFormatAwsError:

    def test_invalid_ami_includes_ami_id_and_region(self):
        err = _make_client_error("InvalidAMIID.NotFound")
        context = {"ami_id": "ami-deadbeef", "region": "us-west-2"}
        msg = format_aws_error(err, context)
        assert "ami-deadbeef" in msg
        assert "us-west-2" in msg

    def test_invalid_ami_defaults_when_context_missing(self):
        err = _make_client_error("InvalidAMIID.NotFound")
        msg = format_aws_error(err, {})
        assert "unknown" in msg  # fallback for missing context

    def test_unauthorized_operation_includes_permission_info(self):
        err = _make_client_error(
            "UnauthorizedOperation",
            "You are not authorized to perform this operation. Encoded authorization failure message.",
        )
        msg = format_aws_error(err, None)
        assert "Insufficient permissions" in msg

    def test_request_limit_exceeded_message(self):
        err = _make_client_error("RequestLimitExceeded")
        msg = format_aws_error(err, None)
        assert "rate limit" in msg.lower()

    def test_unknown_error_code_falls_through(self):
        err = _make_client_error("SomeOtherError", "Something broke")
        msg = format_aws_error(err, None)
        assert "SomeOtherError" in msg
        assert "Something broke" in msg


# ---------------------------------------------------------------------------
# format_credentials_error
# ---------------------------------------------------------------------------

class TestFormatCredentialsError:
    def test_mentions_aws_configure(self):
        msg = format_credentials_error()
        assert "aws configure" in msg

    def test_mentions_env_vars(self):
        msg = format_credentials_error()
        assert "AWS_ACCESS_KEY_ID" in msg
        assert "AWS_SECRET_ACCESS_KEY" in msg


# ---------------------------------------------------------------------------
# retry_on_throttle decorator
# ---------------------------------------------------------------------------

class TestRetryOnThrottle:

    @patch("src.errors.time.sleep")
    def test_succeeds_without_retry(self, mock_sleep):
        """If the function succeeds on the first call, no retries happen."""
        @retry_on_throttle(max_retries=3, base_delay=1.0)
        def ok():
            return "done"

        assert ok() == "done"
        mock_sleep.assert_not_called()

    @patch("src.errors.time.sleep")
    def test_retries_on_throttle_then_succeeds(self, mock_sleep):
        """Retries on RequestLimitExceeded and returns once the call succeeds."""
        call_count = 0

        @retry_on_throttle(max_retries=3, base_delay=1.0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _make_client_error("RequestLimitExceeded")
            return "ok"

        assert flaky() == "ok"
        assert call_count == 3
        # Two sleeps: attempt 0 → sleep(1), attempt 1 → sleep(2)
        assert mock_sleep.call_count == 2

    @patch("src.errors.time.sleep")
    def test_raises_after_max_retries_exhausted(self, mock_sleep):
        """After 3 retries the throttle error is re-raised."""
        @retry_on_throttle(max_retries=3, base_delay=1.0)
        def always_throttled():
            raise _make_client_error("RequestLimitExceeded")

        with pytest.raises(ClientError) as exc_info:
            always_throttled()

        assert exc_info.value.response["Error"]["Code"] == "RequestLimitExceeded"
        # 4 total attempts (0, 1, 2, 3), 3 sleeps before the last attempt
        assert mock_sleep.call_count == 3

    @patch("src.errors.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """Sleep durations follow base_delay * 2^attempt."""
        @retry_on_throttle(max_retries=3, base_delay=0.5)
        def always_throttled():
            raise _make_client_error("RequestLimitExceeded")

        with pytest.raises(ClientError):
            always_throttled()

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [0.5, 1.0, 2.0]  # 0.5*2^0, 0.5*2^1, 0.5*2^2

    @patch("src.errors.time.sleep")
    def test_non_throttle_error_not_retried(self, mock_sleep):
        """Non-throttle ClientErrors are raised immediately without retry."""
        @retry_on_throttle(max_retries=3, base_delay=1.0)
        def bad_ami():
            raise _make_client_error("InvalidAMIID.NotFound", "not found")

        with pytest.raises(ClientError) as exc_info:
            bad_ami()

        assert exc_info.value.response["Error"]["Code"] == "InvalidAMIID.NotFound"
        mock_sleep.assert_not_called()
