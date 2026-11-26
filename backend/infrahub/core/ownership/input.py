from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import GenericSchema
from infrahub.exceptions import SchemaNotFoundError, ValidationError

from .models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    StoredOwnerState,
    field_holder,
)

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

OWNERS_KEY = "owners"
OWNERS_PATH = f"node_metadata.{OWNERS_KEY}"
TARGET_OWNERS_KEY = "target_owners"
TARGET_OWNERS_PATH = f"node_metadata.{TARGET_OWNERS_KEY}"
FIELD_OWNERS_KEY = "field_owners"
TARGET_FIELD_OWNERS_KEY = "target_field_owners"
SOURCES_KEY = "sources"
SOURCES_PATH = f"node_metadata.{SOURCES_KEY}"
OWNER_KINDS = frozenset({InfrahubKind.GENERICACCOUNT, InfrahubKind.ACCOUNTGROUP})
SOURCE_KINDS = OWNER_KINDS | {
    InfrahubKind.GENERICREPOSITORY,
    InfrahubKind.RESOURCEPOOL,
    InfrahubKind.PROFILE,
    InfrahubKind.OBJECTTEMPLATE,
}


@dataclass(frozen=True)
class ReferenceRule:
    """The kinds of node that an input can refer to, and the words that the errors use."""

    kinds: frozenset[str]
    name: str
    a_name: str
    allowed: str

    @property
    def refusal(self) -> str:
        return f"Only {self.allowed} can be {self.a_name}"


OWNER_RULE = ReferenceRule(kinds=OWNER_KINDS, name="owner", a_name="an owner", allowed="an account or an account group")
SOURCE_RULE = ReferenceRule(
    kinds=SOURCE_KINDS,
    name="source",
    a_name="a source",
    allowed="an account, an account group, a repository, a resource pool, a profile or an object template",
)


class OwnerLookup(Protocol):
    async def read_labels(self, node_ids: list[str]) -> dict[str, set[str]]:
        """Return the labels of each node that is active."""
        ...

    async def find_ids_by_hfid(self, kind: str, hfid: list[str]) -> list[str]:
        """Return the IDs of the active nodes of a kind that have this human-friendly ID."""
        ...


async def check_owner_kinds(
    lookup: OwnerLookup, owner_ids: list[str], path: str, rule: ReferenceRule = OWNER_RULE
) -> None:
    """Refuse an owner that is not an active account or account group, or a node that the given rule refuses.

    Raises:
        ValidationError: When a node is not found, or is not of a kind of the rule.

    """
    await check_field_owner_kinds(lookup=lookup, owner_ids={path: owner_ids}, rule=rule)


async def check_field_owner_kinds(
    lookup: OwnerLookup, owner_ids: Mapping[str, list[str]], rule: ReferenceRule = OWNER_RULE
) -> None:
    """Refuse the nodes that several fields give with one read, and name the path of the field in the error.

    Args:
        lookup: The reader of the labels of the nodes.
        owner_ids: The IDs of the nodes that each path gives.
        rule: The kinds of node that the fields can refer to.

    Raises:
        ValidationError: When a node is not found, or is not of a kind of the rule.

    """
    all_ids = list(dict.fromkeys(owner_id for ids in owner_ids.values() for owner_id in ids))
    labels = await lookup.read_labels(node_ids=all_ids) if all_ids else {}
    for path, ids in owner_ids.items():
        for owner_id in ids:
            if owner_id not in labels:
                raise ValidationError({path: f"{rule.name.capitalize()} not found: {owner_id}"})
            if not rule.kinds & labels[owner_id]:
                raise ValidationError({path: f"{rule.refusal}, not: {owner_id}"})


class OwnerInputParser:
    """Read the owners and the sources that a mutation gives, and refuse the whole input when one is not valid."""

    def __init__(self, schema_branch: SchemaBranch, lookup: OwnerLookup) -> None:
        self.schema_branch = schema_branch
        self.lookup = lookup

    async def parse(
        self, node_metadata: Mapping[str, Any], schema: MainSchemaTypes, data: Mapping[str, Any] | None = None
    ) -> dict[HolderKey, StoredOwnerState]:
        """Return the owner state that the input gives to each holder. A key that is left out gives no state.

        The sources of the input are the state of the holder of the sources.

        Args:
            node_metadata: The `node_metadata` input of the mutation.
            schema: The schema of the node that the mutation writes.
            data: The input of the mutation, for the `owners` that it gives next to the value of an attribute.

        Raises:
            ValidationError: When an owner is not found, is not an account or an account group, has an unknown
                kind, has neither an ID, a kind with an HFID, nor a name, or has an HFID of the wrong length. Also
                when a name without a kind is the name of an account and of an account group. The same checks
                apply to a source, with the kinds that can be a source. Also when the input gives owners
                to the nodes of a kind that is not a profile or an object template, or to a field that the kind
                does not have.

        """
        states: dict[HolderKey, StoredOwnerState] = {}
        if OWNERS_KEY in node_metadata:
            owner_ids = await self._owner_ids(value=node_metadata[OWNERS_KEY], path=OWNERS_PATH)
            states[NODE_HOLDER] = StoredOwnerState(owner_ids=owner_ids)
        if SOURCES_KEY in node_metadata:
            source_ids = await self._owner_ids(value=node_metadata[SOURCES_KEY], path=SOURCES_PATH, rule=SOURCE_RULE)
            states[NODE_SOURCES_HOLDER] = StoredOwnerState(owner_ids=source_ids or None)
        gives = [key for key in (TARGET_OWNERS_KEY, TARGET_FIELD_OWNERS_KEY) if key in node_metadata]
        if gives and not (schema.is_profile_schema or schema.is_template_schema):
            raise ValidationError(
                {
                    f"node_metadata.{gives[0]}": (
                        f"Only a profile or an object template gives owners to its nodes, not: {schema.kind}"
                    )
                }
            )
        if TARGET_OWNERS_KEY in node_metadata:
            owner_ids = await self._owner_ids(value=node_metadata[TARGET_OWNERS_KEY], path=TARGET_OWNERS_PATH)
            states[NODE_TARGET_HOLDER] = StoredOwnerState(owner_ids=owner_ids)
        for name, value in (data or {}).items():
            if name in schema.attribute_names and isinstance(value, Mapping) and OWNERS_KEY in value:
                await self._add_field(states=states, schema=schema, field=name, value=value, path=name, target=False)
        for item in node_metadata.get(FIELD_OWNERS_KEY) or []:
            await self._add_field(
                states=states,
                schema=schema,
                field=item.get("field"),
                value=item,
                path=f"node_metadata.{FIELD_OWNERS_KEY}",
                target=False,
            )
        for item in node_metadata.get(TARGET_FIELD_OWNERS_KEY) or []:
            # A profile or an object template gives owners to the fields of the kind that it is for.
            await self._add_field(
                states=states,
                schema=self.schema_branch.get(name=schema.name, duplicate=False),
                field=item.get("field"),
                value=item,
                path=f"node_metadata.{TARGET_FIELD_OWNERS_KEY}",
                target=True,
            )
        return states

    async def _add_field(
        self,
        states: dict[HolderKey, StoredOwnerState],
        schema: MainSchemaTypes,
        field: Any,
        value: Mapping[str, Any],
        path: str,
        target: bool,
    ) -> None:
        holder = field_holder(schema=schema, field_name=field, target=target) if isinstance(field, str) else None
        if holder is None:
            raise ValidationError({path: f"{field} is not an attribute or a relationship of {schema.kind}"})
        owner_ids = await self._owner_ids(value=value.get(OWNERS_KEY), path=f"{path}.{OWNERS_KEY}")
        states[holder] = StoredOwnerState(owner_ids=owner_ids)

    async def _owner_ids(self, value: Any, path: str, rule: ReferenceRule = OWNER_RULE) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not isinstance(value, list | tuple):
            raise ValidationError({path: f"{rule.name.capitalize()}s must be a list"})
        owner_ids: list[str] = []
        given_ids: list[str] = []
        for item in value:
            owner = item if isinstance(item, Mapping) else {}
            owner_id, kind, hfid, name = owner.get("id"), owner.get("kind"), owner.get("hfid"), owner.get("name")
            if isinstance(owner_id, str) and owner_id:
                given_ids.append(owner_id)
                owner_ids.append(owner_id)
            elif isinstance(kind, str) and kind and isinstance(hfid, list | tuple) and hfid:
                owner_ids.append(
                    await self._find_by_hfid(kind=kind, hfid=[str(part) for part in hfid], path=path, rule=rule)
                )
            elif isinstance(name, str) and name:
                owner_ids.append(await self._find_by_name(kind=kind, name=name, path=path, rule=rule))
            else:
                raise ValidationError({path: f"Each {rule.name} must have an id, a kind and an hfid, or a name"})
        await self._check_given_ids(owner_ids=given_ids, path=path, rule=rule)
        return tuple(dict.fromkeys(owner_ids))

    async def _find_by_name(self, kind: Any, name: str, path: str, rule: ReferenceRule) -> str:
        """Return the node of the kind that has this name as its HFID. A name without a kind is an account group.

        Raises:
            ValidationError: When a name without a kind is the name of an account and of an account group.

        """
        if isinstance(kind, str) and kind:
            return await self._find_by_hfid(kind=kind, hfid=[name], path=path, rule=rule)
        group_id = await self._find_by_hfid(kind=InfrahubKind.ACCOUNTGROUP, hfid=[name], path=path, rule=rule)
        if await self.lookup.find_ids_by_hfid(kind=InfrahubKind.GENERICACCOUNT, hfid=[name]):
            raise ValidationError(
                {path: f"{name} is the name of an account and of an account group. Give the kind with the name"}
            )
        return group_id

    async def _find_by_hfid(self, kind: str, hfid: list[str], path: str, rule: ReferenceRule) -> str:
        try:
            schema = self.schema_branch.get(name=kind, duplicate=False)
        except SchemaNotFoundError as exc:
            raise ValidationError({path: f"Unknown kind for {rule.a_name}: {kind}"}) from exc
        kinds = {schema.kind, *([] if isinstance(schema, GenericSchema) else schema.inherit_from)}
        if not kinds & rule.kinds:
            raise ValidationError({path: f"{rule.refusal}, not: {kind}"})
        hfid_length = len(schema.human_friendly_id or [])
        if hfid_length != len(hfid):
            raise ValidationError({path: f"The hfid of {kind} must have {hfid_length} value(s), not {len(hfid)}"})
        node_ids = await self.lookup.find_ids_by_hfid(kind=schema.kind, hfid=hfid)
        if len(node_ids) != 1:
            raise ValidationError({path: f"{rule.name.capitalize()} not found: {kind} {hfid}"})
        return node_ids[0]

    async def _check_given_ids(self, owner_ids: list[str], path: str, rule: ReferenceRule = OWNER_RULE) -> None:
        await check_owner_kinds(lookup=self.lookup, owner_ids=owner_ids, path=path, rule=rule)
