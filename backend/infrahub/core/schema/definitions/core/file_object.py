from infrahub.core.constants import AllowOverrideType

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema

core_file_object = GenericSchema(
    name="FileObject",
    namespace="Core",
    description="A file object for storing and managing file attachments",
    label="File Object",
    include_in_menu=False,
    attributes=[
        Attr(
            name="file_name",
            kind="Text",
            description="The name of the file as uploaded by the user",
            read_only=True,
            optional=False,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="checksum",
            kind="Text",
            description="SHA-1 checksum calculated on the uploaded file",
            read_only=True,
            optional=False,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="file_size",
            kind="Number",
            description="The size of the file in bytes",
            read_only=True,
            optional=False,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="file_type",
            kind="Text",
            description="The MIME type of the file",
            read_only=True,
            optional=False,
            allow_override=AllowOverrideType.NONE,
        ),
        Attr(
            name="storage_id",
            kind="Text",
            description="The ID of the uploaded file in Infrahub's storage",
            optional=False,
            allow_override=AllowOverrideType.NONE,
        ),
    ],
)
