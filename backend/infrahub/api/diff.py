from fastapi import APIRouter


router = APIRouter(prefix="/diff")


@router.get("/data")
async def read_data():
    return {}


@router.get("/files")
async def read_data():
    return {}
