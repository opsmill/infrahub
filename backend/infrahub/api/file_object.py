from __future__ import annotations

import re
import urllib.parse
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
    get_permission_manager,
)
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, PermissionAction
from infrahub.core.protocols import CoreFileObject
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import NodeNotFoundError
from infrahub.permissions import define_object_permission_from_branch

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.permissions import PermissionManager

router = APIRouter(prefix=f"/{InfrahubKind.FILEOBJECT}")


def sanitize_filename(filename: str) -> tuple[str, str]:
    """Sanitize filename to prevent header injection attacks.

    Returns a tuple of (ascii_filename, encoded_filename) for use in Content-Disposition header.
    - ascii_filename: Safe ASCII-only filename for the 'filename' parameter
    - encoded_filename: RFC5987 percent-encoded filename for the 'filename*' parameter
    """
    # Strip control characters (CR, LF, NULL, etc.)
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)

    # Strip/replace characters that could break the header
    filename = filename.replace('"', "'").replace(";", "_")

    # Truncate to reasonable length (255 is common filesystem limit)
    if len(filename) > 255:
        # Keep extension if present
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1][:10]  # Max 10 char extension
            filename = filename[: 255 - len(ext) - 1] + "." + ext
        else:
            filename = filename[:255]

    # Create ASCII-safe fallback (replace non-ASCII with underscore)
    ascii_filename = filename.encode("ascii", errors="replace").decode("ascii").replace("?", "_")

    # RFC5987 percent-encode for filename* parameter
    encoded_filename = urllib.parse.quote(filename, safe="")

    return ascii_filename, encoded_filename


def build_content_disposition(filename: str) -> str:
    """Build a safe Content-Disposition header value.

    https://developer.mozilla.org/docs/Web/HTTP/Reference/Headers/Content-Disposition
    """
    ascii_filename, encoded_filename = sanitize_filename(filename)
    # Use both filename (for older clients) and filename* (for RFC5987 compliant clients)
    return f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"


@router.get("/{storage_id:str}")
async def download_file_object(
    storage_id: str,
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    _: AccountSession = Depends(get_current_user),
) -> Response:
    """Download a file from storage by its storage_id.

    Requires `VIEW` permission on the FileObject node.
    Returns the binary file content with `Content-Type` from the node's `file_type` attribute and `Content-Disposition` header with the original
    filename.
    """
    file_objects = await registry.manager.query(
        db=db,
        schema=CoreFileObject,
        filters={"storage_id__value": storage_id},
        branch=branch_params.branch,
        at=branch_params.at,
        limit=1,
    )
    if not file_objects:
        raise NodeNotFoundError(
            branch_name=branch_params.branch.name, node_type=InfrahubKind.FILEOBJECT, identifier=storage_id
        )

    file_object = file_objects[0]
    permission = define_object_permission_from_branch(
        schema=file_object.get_schema(), action=PermissionAction.VIEW, branch_name=branch_params.branch.name
    )
    permission_manager.raise_for_permission(permission=permission)

    return Response(
        content=registry.storage.retrieve_binary(identifier=storage_id),
        media_type=file_object.file_type.value,
        headers={"Content-Disposition": build_content_disposition(file_object.file_name.value)},
    )
