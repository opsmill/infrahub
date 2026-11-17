from __future__ import annotations

import asyncio
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from starlette.status import HTTP_409_CONFLICT, HTTP_422_UNPROCESSABLE_CONTENT, HTTP_429_TOO_MANY_REQUESTS

from infrahub import config
from infrahub.api.dependencies import get_current_user, get_db, get_permission_manager
from infrahub.core import registry
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import StorageEncryptionError
from infrahub.permissions import PermissionManager  # noqa: TC001
from infrahub.permissions.globals import SUPER_ADMIN_PERMISSION
from infrahub.storage_encryption.artifact_values import store_encrypted_artifact_values
from infrahub.storage_encryption.memory_budget import MemoryBudget, MemoryBudgetBusyError, ProcessMemoryBudget
from infrahub.storage_encryption.migrate import EncryptOutcome, EncryptResult, encrypt_stored_objects

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.storage import InfrahubObjectStorage, StoredObjectListing

LIST_DEFAULT_LIMIT = 1000
LIST_MAX_LIMIT = 5000
BYTES_PER_MEGABYTE = 1024 * 1024
MEMORY_WAIT_SECONDS = 0.5
"""How long a request for one object waits for free encryption memory before it is answered with a 429 response."""
BATCH_MEMORY_WAIT_SECONDS = 60.0
"""How long a file of a batch waits for free encryption memory before the batch is answered with a 429 response."""
MEMORY_RETRY_AFTER_SECONDS = 1
BATCH_MAX_OBJECTS = 500
FORBIDDEN_IDENTIFIER_PARTS = ("/", "\\", "..", "\x00")

router = APIRouter()


class StoredObjectEntry(BaseModel):
    identifier: str
    size: int
    last_modified: datetime


class StoredObjectPage(BaseModel):
    objects: list[StoredObjectEntry]
    next_start_after: str | None


class EncryptObjectResponse(BaseModel):
    identifier: str
    outcome: EncryptOutcome
    size: int
    reason: str | None


class EncryptBatchRequest(BaseModel):
    identifiers: list[str]
    allow_unverified: bool = False


class EncryptBatchResponse(BaseModel):
    results: list[EncryptObjectResponse]


PROCESS_MEMORY_BUDGET = ProcessMemoryBudget()


def memory_budget() -> MemoryBudget:
    """Return the memory budget of this process, sized by the setting."""
    return PROCESS_MEMORY_BUDGET.current(
        capacity=config.SETTINGS.storage.encryption_migration_memory_budget * BYTES_PER_MEGABYTE
    )


class NoFreeMemoryError(HTTPException):
    """The process has no free memory to encrypt a stored object now; the caller retries later."""

    def __init__(self) -> None:
        super().__init__(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail="This server has no free memory to encrypt this stored object now.",
            headers={"Retry-After": str(MEMORY_RETRY_AFTER_SECONDS)},
        )


def validate_identifier(identifier: str) -> None:
    """Refuse a storage identifier that could name a file outside the storage.

    Raises:
        HTTPException: If the identifier contains a path separator, a parent directory reference or a NUL byte.

    """
    if any(part in identifier for part in FORBIDDEN_IDENTIFIER_PARTS):
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The identifier of a stored object cannot contain a path separator or '..'.",
        )


def _list_page(storage: InfrahubObjectStorage, start_after: str | None, limit: int) -> StoredObjectListing:
    if start_after is None:
        # The first page starts a pass over the storage, the moment to clear what an interrupted pass left behind.
        storage.remove_stale_temporary_files()
    return storage.list_page(start_after=start_after, limit=limit)


@router.get("/objects")
async def list_stored_objects(
    start_after: str | None = Query(default=None, description="Return only the objects that sort after this one"),
    limit: int = Query(default=LIST_DEFAULT_LIMIT, ge=1, le=LIST_MAX_LIMIT),
    permission_manager: PermissionManager = Depends(get_permission_manager),
) -> StoredObjectPage:
    """List the stored objects in the order of their identifiers, without reading their content.

    No object is changed, but a request for the first page also deletes the temporary files that an
    interrupted replacement left in the local storage more than an hour ago, and nothing else.

    A page can hold fewer objects than the limit, or none, when an object was deleted while it was read. The
    last page is the one whose `next_start_after` is null: until then, request the next page with it.
    """
    permission_manager.raise_for_permission(permission=SUPER_ADMIN_PERMISSION)

    listing = await asyncio.to_thread(_list_page, registry.storage, start_after or None, limit)
    return StoredObjectPage(
        objects=[
            StoredObjectEntry(identifier=stored.identifier, size=stored.size, last_modified=stored.last_modified)
            for stored in listing.objects
        ],
        next_start_after=listing.next_start_after,
    )


async def _encrypt(
    request: Request,
    db: InfrahubDatabase,
    permission_manager: PermissionManager,
    account: AccountSession,
    identifiers: list[str],
    allow_unverified: bool,
    wait_seconds: float,
) -> list[EncryptResult]:
    """Encrypt the objects, then store `encrypted` on the artifacts that point at them.

    Both steps run in a task that outlives a cancelled request, so an object that was read is still written. A
    failure to store a value does not change the result of its object.

    Raises:
        NoFreeMemoryError: With status 429 when an object waited `wait_seconds` for memory and none was free.
        HTTPException: With status 409 when storage encryption is disabled or this process has no storage key.

    """
    merge_write_blocker = MergeWriteBlocker(cache=request.app.state.service.cache)

    async def encrypt_and_store() -> list[EncryptResult]:
        results = await encrypt_stored_objects(
            db=db,
            storage=registry.storage,
            identifiers=identifiers,
            max_size=config.SETTINGS.storage.encryption_migration_max_size * BYTES_PER_MEGABYTE,
            budget=memory_budget(),
            wait_seconds=wait_seconds,
            allow_unverified=allow_unverified,
        )
        await store_encrypted_artifact_values(
            db=db,
            results=results,
            permission_manager=permission_manager,
            merge_write_blocker=merge_write_blocker,
            user_id=account.account_id,
        )
        return results

    task = asyncio.create_task(encrypt_and_store())
    try:
        return await asyncio.shield(task)
    except StorageEncryptionError as exc:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=exc.message) from exc
    except MemoryBudgetBusyError as exc:
        raise NoFreeMemoryError from exc


def _response(result: EncryptResult) -> EncryptObjectResponse:
    return EncryptObjectResponse(
        identifier=result.identifier, outcome=result.outcome, size=result.size, reason=result.reason
    )


@router.post("/object/{identifier:str}/encrypt")
async def encrypt_stored_object_route(
    request: Request,
    identifier: str,
    allow_unverified: bool = Query(
        default=False, description="Encrypt the object even when no node records a checksum for it"
    ),
    db: InfrahubDatabase = Depends(get_db),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    account: AccountSession = Depends(get_current_user),
) -> EncryptObjectResponse:
    """Encrypt one object that was stored before storage encryption was enabled.

    Raises:
        NoFreeMemoryError: With status 429 when this process has no free memory to hold the object.
        HTTPException: With status 409 when storage encryption is disabled or this process has no storage key.

    """
    permission_manager.raise_for_permission(permission=SUPER_ADMIN_PERMISSION)
    validate_identifier(identifier=identifier)

    (result,) = await _encrypt(
        request=request,
        db=db,
        permission_manager=permission_manager,
        account=account,
        identifiers=[identifier],
        allow_unverified=allow_unverified,
        wait_seconds=MEMORY_WAIT_SECONDS,
    )
    return _response(result)


@router.post("/objects/encrypt")
async def encrypt_stored_objects_route(
    http_request: Request,
    request: EncryptBatchRequest,
    db: InfrahubDatabase = Depends(get_db),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    account: AccountSession = Depends(get_current_user),
) -> EncryptBatchResponse:
    """Encrypt several stored objects, with one lookup of their recorded checksums for the whole request.

    Raises:
        NoFreeMemoryError: With status 429 when an object waited too long for free memory; the objects done by
            then stay encrypted.
        HTTPException: With status 422 when the list is too long or names a forbidden identifier, and with
            status 409 when storage encryption is disabled or this process has no storage key.

    """
    permission_manager.raise_for_permission(permission=SUPER_ADMIN_PERMISSION)
    if not request.identifiers or len(request.identifiers) > BATCH_MAX_OBJECTS:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A request names between 1 and {BATCH_MAX_OBJECTS} stored objects.",
        )
    if len(set(request.identifiers)) != len(request.identifiers):
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail="An identifier is listed twice.")
    for identifier in request.identifiers:
        validate_identifier(identifier=identifier)

    results = await _encrypt(
        request=http_request,
        db=db,
        permission_manager=permission_manager,
        account=account,
        identifiers=request.identifiers,
        allow_unverified=request.allow_unverified,
        wait_seconds=BATCH_MEMORY_WAIT_SECONDS,
    )
    return EncryptBatchResponse(results=[_response(result) for result in results])
