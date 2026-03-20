"""AWS Neptune authentication utilities.

Provides IAM-based authentication for Neptune OpenCypher (Bolt) connections
using AWS SigV4 signing. When IAM auth is disabled, returns a no-auth tuple.
"""

from __future__ import annotations

from infrahub.log import get_logger

log = get_logger()


def get_neptune_auth_token(region: str, endpoint: str, iam_enabled: bool = True) -> tuple[str, str]:
    """Return (username, password) for a Neptune Bolt connection.

    When IAM auth is enabled, uses ``botocore`` to produce a SigV4 pre-signed
    URL that Neptune accepts as the Bolt password (username is left empty).

    When IAM auth is disabled (e.g. in a private VPC with no IAM enforcement),
    returns empty credentials so the neo4j driver connects without auth.
    """
    if not iam_enabled:
        return ("", "")

    try:
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        from botocore.session import Session as BotocoreSession
    except ImportError as exc:
        raise ImportError(
            "botocore is required for Neptune IAM authentication. "
            "Install it with: pip install botocore"
        ) from exc

    session = BotocoreSession()
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError(
            "No AWS credentials found. Configure credentials via environment variables, "
            "AWS profiles, or IAM roles."
        )
    credentials = credentials.get_frozen_credentials()

    # Neptune expects a SigV4-signed request to the neptune-db service
    request = AWSRequest(method="GET", url=f"https://{endpoint}:8182")
    SigV4Auth(credentials, "neptune-db", region).add_auth(request)

    # The signed headers are passed as the password in the Bolt auth
    # Neptune uses the Authorization header as the password
    auth_header = request.headers.get("Authorization", "")
    log.debug("Generated Neptune IAM auth token", region=region, endpoint=endpoint)

    return ("", auth_header)
