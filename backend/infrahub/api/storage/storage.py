from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, File, Response, UploadFile
from infrahub_sdk.uuidt import UUIDT
from pydantic import BaseModel

from infrahub.api.dependencies import get_current_user
from infrahub.core import registry
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

log = get_logger()
router = APIRouter(prefix="/storage")


class UploadResponse(BaseModel):
    identifier: str
    checksum: str


class UploadContentPayload(BaseModel):
    content: str


@router.get("/object/{identifier:str}")
def get_file(identifier: str, _: AccountSession = Depends(get_current_user)) -> Response:
    content = registry.storage.retrieve(identifier=identifier)
    return Response(content=content)


@router.post("/upload/content")
def upload_content(
    item: UploadContentPayload,
    _: str = Depends(get_current_user),
) -> UploadResponse:
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
