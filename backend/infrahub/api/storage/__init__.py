from infrahub.api.storage import file_object
from infrahub.api.storage.storage import router

router.include_router(file_object.router)

__all__ = ["router"]
