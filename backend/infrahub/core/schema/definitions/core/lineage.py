from ...generic_schema import GenericSchema

lineage_owner = GenericSchema(
    name="Owner",
    namespace="Lineage",
    description="Any Entities that is responsible for some data.",
    label="Owner",
    include_in_menu=False,
    documentation="/topics/metadata",
)

lineage_source = GenericSchema(
    name="Source",
    namespace="Lineage",
    description="Any Entities that stores or produces data.",
    label="Source",
    include_in_menu=False,
    documentation="/topics/metadata",
)
