from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from infrahub.message_bus import InfrahubMessage
from infrahub.message_bus.messages.refresh_registry_branches import RefreshRegistryBranches

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent

if TYPE_CHECKING:
    from infrahub.core.models import SchemaDiff


class ChangedElementsPayload(BaseModel):
    """The schema elements added, removed, or changed by a single schema update.

    Carried on a schema-update event so downstream recompute can be scoped to the
    elements that actually changed. JSON-serializable so it survives transport
    through workflow parameters. Absence (``None`` on the event) means the change
    set could not be produced and recompute must fall back to processing everything.
    """

    added_kinds: list[str] = Field(default_factory=list, description="Object-type kinds newly added")
    removed_kinds: list[str] = Field(default_factory=list, description="Object-type kinds removed")
    changed_fields: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Kind to the attribute/relationship names changed on that kind",
    )

    @classmethod
    def from_schema_diff(cls, diff: "SchemaDiff") -> "ChangedElementsPayload":
        """Build the payload from the diff produced when comparing two schemas.

        The diff keys ``added`` / ``changed`` / ``removed`` by kind. For a changed
        kind, attribute and relationship changes are grouped under nested
        ``attributes`` / ``relationships`` buckets whose own ``added`` / ``changed``
        / ``removed`` map the individual element names. Those names are flattened
        here so a change to any read element is recorded; node-level scalar fields
        (e.g. ``label``) are kept under their own name. No further filtering is
        applied, so a cosmetic edit to a read element still counts as a change.
        """
        element_buckets = ("attributes", "relationships")
        changed_fields: dict[str, list[str]] = {}
        for kind, node_diff in diff.changed.items():
            names: set[str] = set()
            for bucket in (node_diff.added, node_diff.changed, node_diff.removed):
                for field_name, nested in bucket.items():
                    if field_name in element_buckets and nested is not None:
                        names.update(nested.added.keys())
                        names.update(nested.changed.keys())
                        names.update(nested.removed.keys())
                    else:
                        names.add(field_name)
            changed_fields[kind] = sorted(names)

        return cls(
            added_kinds=sorted(diff.added.keys()),
            removed_kinds=sorted(diff.removed.keys()),
            changed_fields=changed_fields,
        )


class SchemaUpdatedEvent(InfrahubEvent):
    """Event generated when the schema within a branch has been updated."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.schema.updated"

    branch_name: str = Field(..., description="The name of the branch")
    schema_hash: str = Field(..., description="Schema hash after the update")
    changed_elements: ChangedElementsPayload | None = Field(
        default=None, description="The schema elements changed by the update, when available"
    )

    # NOTE
    # Should schema_update be a branch event ?
    # if feels like the main resource should be the branch

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.schema_branch.{self.branch_name}",
            "infrahub.branch.name": self.branch_name,
            "infrahub.branch.schema_hash": self.schema_hash,
        }

    def get_messages(self) -> list[InfrahubMessage]:
        return [
            RefreshRegistryBranches(),
            # EventSchemaUpdate(
            #     branch=self.branch,
            #     meta=self.get_message_meta(),
            # )
        ]
