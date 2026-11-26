KIND_GRAPHQL_FIELD_NAME = "__kind__"

NODE_METADATA_TYPE = "InfrahubNodeMetadata"
RELATIONSHIP_METADATA_TYPE = "InfrahubRelationshipMetadata"

IS_PROTECTED_DEPRECATION_REASON = "Owners replace `is_protected`. Use `ownership` to read the owners of the attribute."
OWNER_DEPRECATION_REASON = (
    "Use `ownership` to read and `owners` to write the owners of the attribute. "
    "`owner` gives the own owner of the attribute when it has exactly one, else null. "
    "A write of `owner` replaces the own owners of the attribute."
)
