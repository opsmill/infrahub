from __future__ import annotations

import re
import urllib.parse
from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response

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

router = APIRouter(prefix="/files")


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


def build_content_disposition(filename: str, preview: bool = False) -> str:
    """Build a safe Content-Disposition header value.

    https://developer.mozilla.org/docs/Web/HTTP/Reference/Headers/Content-Disposition

    Args:
        filename: The filename to include in the header.
        preview: If True, use 'inline' disposition (display in browser). If False, use 'attachment' (force download).
    """
    ascii_filename, encoded_filename = sanitize_filename(filename)
    disposition = "inline" if preview else "attachment"
    # Use both filename (for older clients) and filename* (for RFC5987 compliant clients)
    return f"{disposition}; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"


def _build_file_response(file_object: CoreFileObject, *, preview: bool = False) -> Response:
    """Build a `Response` for downloading a FileObject's content."""
    return Response(
        content=registry.storage.retrieve_binary(identifier=file_object.storage_id.value),
        media_type=file_object.file_type.value,
        headers={
            "Content-Disposition": build_content_disposition(filename=file_object.file_name.value, preview=preview)
        },
    )


@router.get(
    "/by-hfid/{kind:str}",
    response_class=Response,
    responses={
        200: {
            "description": "File content with Content-Type matching the file's MIME type",
            "content": {"*/*": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def download_file_object_by_hfid(
    kind: str,
    hfid: list[str] = Query(..., description="HFID component values in order"),
    preview: bool = Query(False, description="Return file for inline display rather than as an attachment"),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    _: AccountSession = Depends(get_current_user),
) -> Response:
    """Download a file by the FileObject node's Human-Friendly ID (HFID).

    Requires `VIEW` permission on the FileObject node.
    Returns the binary file content with `Content-Type` from the node's `file_type` attribute and `Content-Disposition` header with the original
    filename.
    """
    schema = registry.schema.get_node_schema(name=kind, branch=branch_params.branch, duplicate=False)

    if InfrahubKind.FILEOBJECT not in schema.inherit_from:
        raise HTTPException(status_code=400, detail=f"'{kind}' is not a file object")

    permission = define_object_permission_from_branch(
        schema=schema, action=PermissionAction.VIEW, branch_name=branch_params.branch.name
    )
    permission_manager.raise_for_permission(permission=permission)

    node = await registry.manager.get_one_by_hfid(
        db=db, hfid=hfid, kind=kind, branch=branch_params.branch, at=branch_params.at, raise_on_error=True
    )

    return _build_file_response(file_object=cast("CoreFileObject", node), preview=preview)


@router.get(
    "/by-storage-id/{storage_id:str}",
    response_class=Response,
    responses={
        200: {
            "description": "File content with Content-Type matching the file's MIME type",
            "content": {"*/*": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def download_file_object_by_storage_id(
    storage_id: str,
    preview: bool = Query(False, description="Return file for inline display rather than as an attachment"),
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

    node = file_objects[0]
    permission = define_object_permission_from_branch(
        schema=node.get_schema(), action=PermissionAction.VIEW, branch_name=branch_params.branch.name
    )
    permission_manager.raise_for_permission(permission=permission)

    return _build_file_response(file_object=node, preview=preview)


@router.get(
    "/{node_id:str}",
    response_class=Response,
    responses={
        200: {
            "description": "File content with Content-Type matching the file's MIME type",
            "content": {"*/*": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def download_file_object(
    node_id: str,
    preview: bool = Query(False, description="Return file for inline display rather than as an attachment"),
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    _: AccountSession = Depends(get_current_user),
) -> Response:
    """Download a file by the FileObject node's UUID.

    Requires `VIEW` permission on the FileObject node.
    Returns the binary file content with `Content-Type` from the node's `file_type` attribute and `Content-Disposition` header with the original
    filename.
    """
    node = await registry.manager.get_one(
        db=db, id=node_id, kind=CoreFileObject, branch=branch_params.branch, at=branch_params.at, raise_on_error=True
    )

    permission = define_object_permission_from_branch(
        schema=node.get_schema(), action=PermissionAction.VIEW, branch_name=branch_params.branch.name
    )
    permission_manager.raise_for_permission(permission=permission)

    return _build_file_response(file_object=node, preview=preview)
