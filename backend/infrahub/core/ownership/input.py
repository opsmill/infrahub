from __future__ import annotations

from collections import defaultdict
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

    async def find_ids_by_hfids(self, kind: str, hfids: list[tuple[str, ...]]) -> dict[tuple[str, ...], list[str]]:
        """Return the IDs of the active nodes of a kind that have each of these human-friendly IDs."""
        ...


@dataclass(frozen=True)
class HfidReference:
    """A node that an input gives by its kind and its human-friendly ID."""

    kind: str
    hfid: tuple[str, ...]


@dataclass
class GivenOwners:
    """The owner list that an input gives to one holder, before the lookups in the database.

    Each reference is an ID or a kind with an HFID.
    """

    path: str
    rule: ReferenceRule
    references: list[str | HfidReference]


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
    labels = await _read_labels(lookup=lookup, owner_ids=[owner_id for ids in owner_ids.values() for owner_id in ids])
    for path, ids in owner_ids.items():
        _refuse_kinds(labels=labels, owner_ids=ids, path=path, rule=rule)


async def _read_labels(lookup: OwnerLookup, owner_ids: list[str]) -> dict[str, set[str]]:
    unique_ids = list(dict.fromkeys(owner_ids))
    return await lookup.read_labels(node_ids=unique_ids) if unique_ids else {}


def _refuse_kinds(labels: Mapping[str, set[str]], owner_ids: list[str], path: str, rule: ReferenceRule) -> None:
    for owner_id in owner_ids:
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

        A field entry that leaves out `owners` gives no state either. The sources of the input are the state of
        the holder of the sources.

        Args:
            node_metadata: The `node_metadata` input of the mutation.
            schema: The schema of the node that the mutation writes.
            data: The input of the mutation, for the `owners` that it gives next to the value of an attribute.

        Raises:
            ValidationError: When an owner is not found, is not an account or an account group, has an unknown
                kind, has neither an ID, a kind with an HFID, nor a kind with a name, has a name without a kind,
                or has an HFID of the wrong length. The same checks apply to a source, with the kinds that can be
                a source. Also when the input gives owners to the nodes of a kind that is not a profile or an
                object template, or names a field that the kind does not have.

        """
        given: list[tuple[HolderKey, GivenOwners | None]] = []
        if OWNERS_KEY in node_metadata:
            given.append((NODE_HOLDER, self._given_owners(value=node_metadata[OWNERS_KEY], path=OWNERS_PATH)))
        if SOURCES_KEY in node_metadata:
            given.append(
                (
                    NODE_SOURCES_HOLDER,
                    self._given_owners(value=node_metadata[SOURCES_KEY], path=SOURCES_PATH, rule=SOURCE_RULE),
                )
            )
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
            given.append(
                (
                    NODE_TARGET_HOLDER,
                    self._given_owners(value=node_metadata[TARGET_OWNERS_KEY], path=TARGET_OWNERS_PATH),
                )
            )
        given.extend(
            entry
            for name, value in (data or {}).items()
            if name in schema.attribute_names and isinstance(value, Mapping)
            if (entry := self._given_field(schema=schema, field=name, value=value, path=name)) is not None
        )
        given.extend(
            entry
            for item in node_metadata.get(FIELD_OWNERS_KEY) or []
            if (
                entry := self._given_field(
                    schema=schema, field=item.get("field"), value=item, path=f"node_metadata.{FIELD_OWNERS_KEY}"
                )
            )
            is not None
        )
        # A profile or an object template gives owners to the fields of the kind that it is for.
        given.extend(
            entry
            for item in node_metadata.get(TARGET_FIELD_OWNERS_KEY) or []
            if (
                entry := self._given_field(
                    schema=self.schema_branch.get(name=schema.name, duplicate=False),
                    field=item.get("field"),
                    value=item,
                    path=f"node_metadata.{TARGET_FIELD_OWNERS_KEY}",
                    target=True,
                )
            )
            is not None
        )
        resolved = iter(await self._resolve(given_lists=[owners for _, owners in given if owners is not None]))
        states: dict[HolderKey, StoredOwnerState] = {}
        for holder, owners in given:
            owner_ids = next(resolved) if owners is not None else None
            if holder == NODE_SOURCES_HOLDER:
                owner_ids = owner_ids or None
            states[holder] = StoredOwnerState(owner_ids=owner_ids)
        return states

    def _given_field(
        self, schema: MainSchemaTypes, field: Any, value: Mapping[str, Any], path: str, target: bool = False
    ) -> tuple[HolderKey, GivenOwners | None] | None:
        holder = field_holder(schema=schema, field_name=field, target=target) if isinstance(field, str) else None
        if holder is None:
            raise ValidationError({path: f"{field} is not an attribute or a relationship of {schema.kind}"})
        if OWNERS_KEY not in value:
            return None
        return holder, self._given_owners(value=value.get(OWNERS_KEY), path=f"{path}.{OWNERS_KEY}")

    def _given_owners(self, value: Any, path: str, rule: ReferenceRule = OWNER_RULE) -> GivenOwners | None:
        if value is None:
            return None
        if not isinstance(value, list | tuple):
            raise ValidationError({path: f"{rule.name.capitalize()}s must be a list"})
        given = GivenOwners(path=path, rule=rule, references=[])
        for item in value:
            owner = item if isinstance(item, Mapping) else {}
            owner_id, kind, hfid, name = owner.get("id"), owner.get("kind"), owner.get("hfid"), owner.get("name")
            if isinstance(owner_id, str) and owner_id:
                given.references.append(owner_id)
            elif isinstance(kind, str) and kind and isinstance(hfid, list | tuple) and hfid:
                given.references.append(
                    self._hfid_reference(kind=kind, hfid=[str(part) for part in hfid], path=path, rule=rule)
                )
            elif isinstance(kind, str) and kind and isinstance(name, str) and name:
                given.references.append(self._hfid_reference(kind=kind, hfid=[name], path=path, rule=rule))
            elif isinstance(name, str) and name:
                raise ValidationError({path: f"Give the kind with the name of {rule.a_name}: {name}"})
            else:
                raise ValidationError(
                    {path: f"Each {rule.name} must have an id, a kind and an hfid, or a kind and a name"}
                )
        return given

    def _hfid_reference(self, kind: str, hfid: list[str], path: str, rule: ReferenceRule) -> HfidReference:
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
        return HfidReference(kind=schema.kind, hfid=tuple(hfid))

    async def _resolve(self, given_lists: list[GivenOwners]) -> list[tuple[str, ...]]:
        """Return the owner IDs of each list, with one read of the given IDs and one HFID read for each kind.

        Raises:
            ValidationError: When a node is not found, or has a kind that the rule of its list refuses.

        """
        hfids_by_kind: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        for given in given_lists:
            for reference in given.references:
                if isinstance(reference, HfidReference):
                    hfids_by_kind[reference.kind].add(reference.hfid)
        found: dict[str, dict[tuple[str, ...], list[str]]] = {}
        for kind, hfids in hfids_by_kind.items():
            found[kind] = await self.lookup.find_ids_by_hfids(kind=kind, hfids=sorted(hfids))
        labels = await _read_labels(
            lookup=self.lookup,
            owner_ids=[
                reference for given in given_lists for reference in given.references if isinstance(reference, str)
            ],
        )
        resolved: list[tuple[str, ...]] = []
        for given in given_lists:
            owner_ids: list[str] = []
            for reference in given.references:
                if isinstance(reference, str):
                    owner_ids.append(reference)
                    continue
                node_ids = found[reference.kind].get(reference.hfid, [])
                if len(node_ids) != 1:
                    message = f"{given.rule.name.capitalize()} not found: {reference.kind} {list(reference.hfid)}"
                    raise ValidationError({given.path: message})
                owner_ids.append(node_ids[0])
            _refuse_kinds(
                labels=labels,
                owner_ids=[reference for reference in given.references if isinstance(reference, str)],
                path=given.path,
                rule=given.rule,
            )
            resolved.append(tuple(dict.fromkeys(owner_ids)))
        return resolved
