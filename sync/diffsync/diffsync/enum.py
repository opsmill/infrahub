"""DiffSync enums and flags.

Copyright (c) 2020 Network To Code, LLC <info@networktocode.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import enum


class DiffSyncModelFlags(enum.Flag):
    """Flags that can be set on a DiffSyncModel class or instance to affect its usage."""

    NONE = 0

    IGNORE = 0b1
    """Do not render diffs containing this model; do not make any changes to this model when synchronizing.

    Can be used to indicate a model instance that exists but should not be changed by DiffSync.
    """

    SKIP_CHILDREN_ON_DELETE = 0b10
    """When deleting this model, do not recursively delete its children.

    Can be used for the case where deletion of a model results in the automatic deletion of all its children.
    """

    SKIP_UNMATCHED_SRC = 0b100
    """Ignore the model if it only exists in the source/"from" DiffSync when determining diffs and syncing.

    If this flag is set, no new model will be created in the target/"to" DiffSync.
    """

    SKIP_UNMATCHED_DST = 0b1000
    """Ignore the model if it only exists in the target/"to" DiffSync when determining diffs and syncing.

    If this flag is set, the model will not be deleted from the target/"to" DiffSync.
    """

    SKIP_UNMATCHED_BOTH = SKIP_UNMATCHED_SRC | SKIP_UNMATCHED_DST


class DiffSyncFlags(enum.Flag):
    """Flags that can be passed to a sync_* or diff_* call to affect its behavior."""

    NONE = 0

    CONTINUE_ON_FAILURE = 0b1
    """Continue synchronizing even if failures are encountered when syncing individual models."""

    SKIP_UNMATCHED_SRC = 0b10
    """Ignore objects that only exist in the source/"from" DiffSync when determining diffs and syncing.

    If this flag is set, no new objects will be created in the target/"to" DiffSync.
    """

    SKIP_UNMATCHED_DST = 0b100
    """Ignore objects that only exist in the target/"to" DiffSync when determining diffs and syncing.

    If this flag is set, no objects will be deleted from the target/"to" DiffSync.
    """

    SKIP_UNMATCHED_BOTH = SKIP_UNMATCHED_SRC | SKIP_UNMATCHED_DST

    LOG_UNCHANGED_RECORDS = 0b1000
    """If this flag is set, a log message will be generated during synchronization for each model, even unchanged ones.

    By default, when this flag is unset, only models that have actual changes to synchronize will be logged.
    This flag is off by default to reduce the default verbosity of DiffSync, but can be enabled when debugging.
    """


class DiffSyncStatus(enum.Enum):
    """Flag values to set as a DiffSyncModel's `_status` when performing a sync; values are logged by DiffSyncSyncer."""

    UNKNOWN = "unknown"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class DiffSyncActions:  # pylint: disable=too-few-public-methods
    """List of valid Action for DiffSyncModel."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SKIP = "skip"
    NO_CHANGE = None
