from types import MappingProxyType
from typing import Final, Mapping

COMMITS_DIRECTORY_NAME = "commits"
BRANCHES_DIRECTORY_NAME = "branches"
TEMPORARY_DIRECTORY_NAME = "temp"

READ_ONLY_FETCH_TIMEOUT_SECONDS: Final = 900
"""Ceiling on a read-only repository's fetch, after which git and every process it started are told
to stop. Generous: a first transfer of a large repository is legitimately slow."""

READ_ONLY_FETCH_STOP_GRACE_SECONDS: Final = 10
"""How long a fetch told to stop has to exit, removing its lock files, before it is killed outright."""

# git applies no network timeout of its own. These end an HTTP transfer that has stalled below a
# trickle; every transport, SSH included, is bounded instead by the kill timeout git is given.
REMOTE_TRANSPORT_ENVIRONMENT: Final[Mapping[str, str]] = MappingProxyType(
    {"GIT_HTTP_LOW_SPEED_LIMIT": "1000", "GIT_HTTP_LOW_SPEED_TIME": "20"}
)

# Ref targeted by the write-access probe. The probe never mutates the remote because it runs under
# --dry-run; this name is merely improbable, so the probe is meaningful even on a remote that happens
# to hold a branch by this name.
WRITE_ACCESS_PROBE_REF = "infrahub-write-access-probe-do-not-create"
