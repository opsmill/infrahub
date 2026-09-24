from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from infrahub_sdk.uuidt import UUIDT
from pydantic import BaseModel

from infrahub.api.dependencies import get_current_user, get_db
from infrahub.api.storage import file_object
from infrahub.artifacts.checksum import compute_artifact_checksum
from infrahub.artifacts.integrity import (
    ARTIFACT_LABEL,
    ArtifactChecksumResolver,
    get_artifact_checksum_resolver,
    request_artifact_regeneration,
    verify_content,
)
from infrahub.core import registry
from infrahub.core.protocols import CoreFileObject
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import StorageObjectIntegrityError

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession


router = APIRouter(prefix="/storage")
router.include_router(file_object.router)


class UploadResponse(BaseModel):
    identifier: str
    checksum: str


class UploadContentPayload(BaseModel):
    content: str


@router.get("/object/{identifier:str}")
async def get_file(
    identifier: str,
    request: Request,
    db: InfrahubDatabase = Depends(get_db),
    checksum_resolver: ArtifactChecksumResolver = Depends(get_artifact_checksum_resolver),
    account_session: AccountSession = Depends(get_current_user),
) -> Response:
    if await registry.manager.query(db=db, schema=CoreFileObject, filters={"storage_id__value": identifier}, limit=1):
        file_url = request.url_for("download_file_object_by_storage_id", storage_id=identifier)
        raise HTTPException(status_code=403, detail=f"Use {file_url.path} instead.")

    content = registry.storage.retrieve_binary(identifier=identifier)
    if recorded := await checksum_resolver.get_recorded_checksums(db=db, storage_id=identifier):
        try:
            verify_content(
                storage_id=identifier,
                content=content,
                expected_checksums={item.checksum for item in recorded},
                compute=compute_artifact_checksum,
                object_label=ARTIFACT_LABEL,
            )
        except StorageObjectIntegrityError:
            await request_artifact_regeneration(
                db=db, service=request.app.state.service, account=account_session, recorded=recorded
            )
            raise
    return Response(content=content)


@router.post("/upload/content")
def upload_content(item: UploadContentPayload, _: str = Depends(get_current_user)) -> UploadResponse:
    file_content = bytes(item.content, encoding="utf-8")
    identifier = str(UUIDT())

    checksum = hashlib.md5(file_content, usedforsecurity=False).hexdigest()
    registry.storage.store(identifier=identifier, content=io.BytesIO(file_content))
    return UploadResponse(identifier=identifier, checksum=checksum)


@router.post("/upload/file")
def upload_file(file: UploadFile = File(...), _: AccountSession = Depends(get_current_user)) -> UploadResponse:
    identifier = str(UUIDT())

    hasher = hashlib.md5(usedforsecurity=False)
    while chunk := file.file.read(65536):
        hasher.update(chunk)
    checksum = hasher.hexdigest()

    file.file.seek(0)
    registry.storage.store(identifier=identifier, content=file.file)
    return UploadResponse(identifier=identifier, checksum=checksum)
