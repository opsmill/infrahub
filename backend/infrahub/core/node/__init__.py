from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Sequence, TypeVar, overload

from infrahub_sdk.template import Jinja2Template
from infrahub_sdk.utils import is_valid_uuid
from infrahub_sdk.uuidt import UUIDT

from infrahub.core import registry
from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    OBJECT_TEMPLATE_NAME_ATTR,
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    BranchSupportType,
    ComputedAttributeKind,
    InfrahubKind,
    NumberPoolType,
    RelationshipCardinality,
    RelationshipKind,
)
from infrahub.core.constants.schema import SchemaElementPathType
from infrahub.core.protocols import CoreNumberPool, CoreObjectTemplate
from infrahub.core.query.node import NodeCheckIDQuery, NodeCreateAllQuery, NodeDeleteQuery, NodeGetListQuery
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    NonGenericSchemaTypes,
    ProfileSchema,
    RelationshipSchema,
    TemplateSchema,
)
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError, NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.types import ATTRIBUTE_TYPES

from ...graphql.constants import KIND_GRAPHQL_FIELD_NAME
from ...graphql.models import OrderModel
from ...log import get_logger
from ..query.relationship import RelationshipDeleteAllQuery
from ..relationship import RelationshipManager
from ..utils import update_relationships_to
from .base import BaseNode, BaseNodeMeta, BaseNodeOptions

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..attribute import BaseAttribute

SchemaProtocol = TypeVar("SchemaProtocol")

# ---------------------------------------------------------------------------------------
# Type of Nodes
#  - Core node, wo/ branch : Branch, MergeRequest, Comment
#  - Core node, w/ branch : Repository, GQLQuery, Permission, Account, Groups, Schema
#  - Location Node : Location,
#  - Select Node : Status, Role, Manufacturer etc ..
#  -
# ---------------------------------------------------------------------------------------

log = get_logger()


class Node(BaseNode, metaclass=BaseNodeMeta):
    @classmethod
    def __init_subclass_with_meta__(cls, _meta=None, default_filter=None, **options) -> None:
        if not _meta:
            _meta = BaseNodeOptions(cls)

        _meta.default_filter = default_filter
        super().__init_subclass_with_meta__(_meta=_meta, **options)

    def get_schema(self) -> NonGenericSchemaTypes:
        return self._schema

    def get_kind(self) -> str:
        """Return the main Kind of the Object."""
        return self._schema.kind

    def get_id(self) -> str:
        """Return the ID of the node"""
        if self.id:
            return self.id

        raise InitializationError("The node has not been saved yet and doesn't have an id")

    def get_updated_at(self) -> Timestamp | None:
        return self._updated_at

    async def get_hfid(self, db: InfrahubDatabase, include_kind: bool = False) -> list[str] | None:
        """Return the Human friendly id of the node."""
        if not self._schema.human_friendly_id:
            return None

        hfid_values = [await self.get_path_value(db=db, path=item) for item in self._schema.human_friendly_id]
        hfid = [value for value in hfid_values if value is not None]
        if include_kind:
            return [self.get_kind()] + hfid
        return hfid

    async def get_hfid_as_string(self, db: InfrahubDatabase, include_kind: bool = False) -> str | None:
        """Return the Human friendly id of the node in string format separated with a dunder (__) ."""
        hfid = await self.get_hfid(db=db, include_kind=include_kind)
        if not hfid:
            return None
        return "__".join(hfid)

    async def get_path_value(self, db: InfrahubDatabase, path: str) -> str:
        schema_path = self._schema.parse_schema_path(
            path=path, schema=db.schema.get_schema_branch(name=self._branch.name)
        )

        if not schema_path.has_property:
            raise ValueError(f"Unable to retrieve the value of a path without property {path!r} on {self.get_kind()!r}")

        if (
            schema_path.is_type_relationship
            and schema_path.relationship_schema.cardinality == RelationshipCardinality.MANY
        ):
            raise ValueError(
                f"Unable to retrieve the value of a path on a relationship of cardinality many {path!r} on {self.get_kind()!r}"
            )

        if schema_path.is_type_attribute:
            attr = getattr(self, schema_path.attribute_schema.name)
            return getattr(attr, schema_path.attribute_property_name)

        if schema_path.is_type_relationship:
            relm: RelationshipManager = getattr(self, schema_path.relationship_schema.name)
            await relm.resolve(db=db)
            node = await relm.get_peer(db=db)
            attr = getattr(node, schema_path.attribute_schema.name)
            return getattr(attr, schema_path.attribute_property_name)

    def get_labels(self) -> list[str]:
        """Return the labels for this object, composed of the kind
        and the list of Generic this object is inheriting from."""
        labels: list[str] = []
        if isinstance(self._schema, NodeSchema):
            labels = [self.get_kind()] + self._schema.inherit_from
            if (
                self._schema.namespace not in ["Schema", "Internal"]
                and InfrahubKind.GENERICGROUP not in self._schema.inherit_from
            ):
                labels.append(InfrahubKind.NODE)
            return labels

        if isinstance(self._schema, ProfileSchema | TemplateSchema):
            labels = [self.get_kind()] + self._schema.inherit_from
            return labels

        return [self.get_kind()]

    def get_branch_based_on_support_type(self) -> Branch:
        """If the attribute is branch aware, return the Branch object associated with this attribute
        If the attribute is branch agnostic return the Global Branch

        Returns:
            Branch:
        """
        if self._schema.branch == BranchSupportType.AGNOSTIC:
            return registry.get_global_branch()
        return self._branch

    def __repr__(self) -> str:
        if not self._existing:
            return f"{self.get_kind()}(ID: {str(self.id)})[NEW]"

        return f"{self.get_kind()}(ID: {str(self.id)})"

    def __init__(self, schema: NodeSchema | ProfileSchema | TemplateSchema, branch: Branch, at: Timestamp):
        self._schema: NodeSchema | ProfileSchema | TemplateSchema = schema
        self._branch: Branch = branch
        self._at: Timestamp = at
        self._existing: bool = False

        self._updated_at: Timestamp | None = None
        self.id: str = None
        self.db_id: str = None

        self._source: Node | None = None
        self._owner: Node | None = None
        self._is_protected: bool = None
        self._computed_jinja2_attributes: list[str] = []

        # Lists of attributes and relationships names
        self._attributes: list[str] = []
        self._relationships: list[str] = []
        self._node_changelog: NodeChangelog | None = None

    @property
    def node_changelog(self) -> NodeChangelog:
        if self._node_changelog:
            return self._node_changelog

        raise InitializationError("The node has not been saved so no changelog exists")

    @overload
    @classmethod
    async def init(
        cls,
        schema: NodeSchema | ProfileSchema | TemplateSchema | str,
        db: InfrahubDatabase,
        branch: Branch | str | None = ...,
        at: Timestamp | str | None = ...,
    ) -> Self: ...

    @overload
    @classmethod
    async def init(
        cls,
        schema: type[SchemaProtocol],
        db: InfrahubDatabase,
        branch: Branch | str | None = ...,
        at: Timestamp | str | None = ...,
    ) -> SchemaProtocol: ...

    @classmethod
    async def init(
        cls,
        schema: NodeSchema | ProfileSchema | TemplateSchema | str | type[SchemaProtocol],
        db: InfrahubDatabase,
        branch: Branch | str | None = None,
        at: Timestamp | str | None = None,
    ) -> Self | SchemaProtocol:
        attrs: dict[str, Any] = {}

        branch = await registry.get_branch(branch=branch, db=db)

        if isinstance(schema, NodeSchema | ProfileSchema | TemplateSchema):
            attrs["schema"] = schema
        elif isinstance(schema, str):
            # TODO need to raise a proper exception for this, right now it will raise a generic ValueError
            attrs["schema"] = db.schema.get(name=schema, branch=branch)
        elif hasattr(schema, "_is_runtime_protocol") and schema._is_runtime_protocol:
            attrs["schema"] = db.schema.get(name=schema.__name__, branch=branch)
        else:
            raise ValueError(
                f"Invalid schema provided {type(schema)}, expected NodeSchema, ProfileSchema or TemplateSchema"
            )

        attrs["branch"] = branch
        attrs["at"] = Timestamp(at)

        return cls(**attrs)

    async def handle_pool(self, db: InfrahubDatabase, attribute: BaseAttribute, errors: list) -> None:
        """Evaluate if a resource has been requested from a pool and apply the resource

        This method only works on number pools, currently Integer is the only type that has the from_pool
        within the create code.
        """

        number_pool_parameters: NumberPoolParameters | None = None
        if attribute.schema.kind == "NumberPool" and isinstance(attribute.schema.parameters, NumberPoolParameters):
            attribute.from_pool = {"id": attribute.schema.parameters.number_pool_id}
            attribute.is_default = False
            number_pool_parameters = attribute.schema.parameters

        if not attribute.from_pool:
            return

        try:
            number_pool = await registry.manager.get_one_by_id_or_default_filter(
                db=db, id=attribute.from_pool["id"], kind=CoreNumberPool
            )
        except NodeNotFoundError:
            if number_pool_parameters:
                number_pool = await self._create_number_pool(
                    db=db, attribute=attribute, number_pool_parameters=number_pool_parameters
                )

            else:
                errors.append(
                    ValidationError(
                        {f"{attribute.name}.from_pool": f"The pool requested {attribute.from_pool} was not found."}
                    )
                )
                return

        if (
            number_pool.node.value in [self._schema.kind] + self._schema.inherit_from
            and number_pool.node_attribute.value == attribute.name
        ):
            try:
                next_free = await number_pool.get_resource(db=db, branch=self._branch, node=self, attribute=attribute)
            except PoolExhaustedError:
                errors.append(
                    ValidationError({f"{attribute.name}.from_pool": f"The pool {number_pool.node.value} is exhausted."})
                )
                return

            attribute.value = next_free
            attribute.source = number_pool.id
        else:
            errors.append(
                ValidationError(
                    {
                        f"{attribute.name}.from_pool": f"The {number_pool.name.value} pool can't be used for '{attribute.name}'."
                    }
                )
            )

    async def _create_number_pool(
        self, db: InfrahubDatabase, attribute: BaseAttribute, number_pool_parameters: NumberPoolParameters
    ) -> CoreNumberPool:
        schema = db.schema.get_node_schema(name="CoreNumberPool", duplicate=False)

        pool_node = self._schema.kind
        schema_attribute = self._schema.get_attribute(attribute.schema.name)
        if schema_attribute.inherited:
            for generic_name in self._schema.inherit_from:
                generic_node = db.schema.get_generic_schema(name=generic_name, duplicate=False)
                if attribute.schema.name in generic_node.attribute_names:
                    pool_node = generic_node.kind
                    break

        number_pool = await Node.init(db=db, schema=schema, branch=self._branch)
        await number_pool.new(
            db=db,
            id=number_pool_parameters.number_pool_id,
            name=f"{pool_node}.{attribute.schema.name} [{number_pool_parameters.number_pool_id}]",
            node=pool_node,
            node_attribute=attribute.schema.name,
            start_range=number_pool_parameters.start_range,
            end_range=number_pool_parameters.end_range,
            pool_type=NumberPoolType.SCHEMA.value,
        )
        await number_pool.save(db=db)
        # Do a lookup of the number pool to get the correct mapped type from the registry
        # without this we don't get access to the .get_resource() method.
        return await registry.manager.get_one_by_id_or_default_filter(db=db, id=number_pool.id, kind=CoreNumberPool)

    async def handle_object_template(self, fields: dict, db: InfrahubDatabase, errors: list) -> None:
        """Fill the `fields` parameters with values from an object template if one is in use."""
        object_template_field = fields.get(OBJECT_TEMPLATE_RELATIONSHIP_NAME)
        if not object_template_field:
            return

        try:
            template: CoreObjectTemplate = await registry.manager.find_object(
                db=db,
                kind=self._schema.get_relationship(name=OBJECT_TEMPLATE_RELATIONSHIP_NAME).peer,
                id=object_template_field.get("id"),
                hfid=object_template_field.get("hfid"),
                branch=self.get_branch_based_on_support_type(),
            )
        except NodeNotFoundError:
            errors.append(
                ValidationError(
                    {
                        f"{OBJECT_TEMPLATE_RELATIONSHIP_NAME}": (
                            "Unable to find the object template in the database "
                            f"'{object_template_field.get('id') or object_template_field.get('hfid')}'"
                        )
                    }
                )
            )
            return

        # Handle attributes, copy values from template
        # Relationships handling in performed in GraphQL mutation to create nodes for relationships
        for attribute_name in template._attributes:
            if attribute_name in list(fields) + [OBJECT_TEMPLATE_NAME_ATTR]:
                continue
            fields[attribute_name] = {"value": getattr(template, attribute_name).value, "source": template.id}

        for relationship_name in template._relationships:
            relationship_schema = template._schema.get_relationship(name=relationship_name)
            if (
                relationship_name in list(fields)
                or relationship_schema.kind not in [RelationshipKind.ATTRIBUTE, RelationshipKind.GENERIC]
                or relationship_name == OBJECT_TEMPLATE_RELATIONSHIP_NAME
            ):
                continue

            relationship: RelationshipManager = getattr(template, relationship_name)
            if relationship_schema.cardinality == RelationshipCardinality.ONE:
                if relationship_peer := await relationship.get_peer(db=db):
                    fields[relationship_name] = {"id": relationship_peer.id}
            elif relationship_peers := await relationship.get_peers(db=db):
                fields[relationship_name] = [{"id": peer_id} for peer_id in relationship_peers]

    async def _process_fields(self, fields: dict, db: InfrahubDatabase) -> None:
        errors = []

        if "_source" in fields.keys():
            self._source = fields["_source"]
        if "_owner" in fields.keys():
            self._owner = fields["_owner"]

        # -------------------------------------------
        # Validate Input
        # -------------------------------------------
        if "updated_at" in fields and "updated_at" not in self._schema.valid_input_names:
            # FIXME: Allow users to use "updated_at" named attributes until we have proper metadata handling
            fields.pop("updated_at")
        for field_name in fields.keys():
            if field_name not in self._schema.valid_input_names:
                log.error(f"{field_name} is not a valid input for {self.get_kind()}")

        # Backfill fields with the ones from the template if there's one
        await self.handle_object_template(fields=fields, db=db, errors=errors)

        # If the object is new, we need to ensure that all mandatory attributes and relationships have been provided
        if not self._existing:
            for mandatory_attr in self._schema.mandatory_attribute_names:
                if mandatory_attr not in fields.keys():
                    if self._schema.is_node_schema:
                        mandatory_attribute = self._schema.get_attribute(name=mandatory_attr)
                        if (
                            mandatory_attribute.computed_attribute
                            and mandatory_attribute.computed_attribute.kind == ComputedAttributeKind.JINJA2
                        ):
                            self._computed_jinja2_attributes.append(mandatory_attr)
                            continue

                        if mandatory_attribute.kind == "NumberPool":
                            continue

                    errors.append(
                        ValidationError({mandatory_attr: f"{mandatory_attr} is mandatory for {self.get_kind()}"})
                    )

            for mandatory_rel in self._schema.mandatory_relationship_names:
                if mandatory_rel not in fields.keys():
                    errors.append(
                        ValidationError({mandatory_rel: f"{mandatory_rel} is mandatory for {self.get_kind()}"})
                    )

        if errors:
            raise ValidationError(errors)

        # -------------------------------------------
        # Generate Attribute and Relationship and assign them
        # -------------------------------------------
        errors.extend(await self._process_fields_relationships(fields=fields, db=db))
        errors.extend(await self._process_fields_attributes(fields=fields, db=db))

        if errors:
            raise ValidationError(errors)

        # Check if any post processor have been defined
        # A processor can be used for example to assigne a default value
        for name in self._attributes + self._relationships:
            if hasattr(self, f"process_{name}"):
                await getattr(self, f"process_{name}")(db=db)

    async def _process_fields_relationships(self, fields: dict, db: InfrahubDatabase) -> list[ValidationError]:
        errors: list[ValidationError] = []

        for rel_schema in self._schema.relationships:
            self._relationships.append(rel_schema.name)

            # Check if there is a more specific generator present
            # Otherwise use the default generator
            generator_method_name = "_generate_relationship_default"
            if hasattr(self, f"generate_{rel_schema.name}"):
                generator_method_name = f"generate_{rel_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    rel_schema.name,
                    await generator_method(
                        db=db, name=rel_schema.name, schema=rel_schema, data=fields.get(rel_schema.name, None)
                    ),
                )
            except ValidationError as exc:
                errors.append(exc)

        return errors

    async def _process_fields_attributes(self, fields: dict, db: InfrahubDatabase) -> list[ValidationError]:
        errors: list[ValidationError] = []

        for attr_schema in self._schema.attributes:
            self._attributes.append(attr_schema.name)
            if not self._existing and attr_schema.name in self._computed_jinja2_attributes:
                continue

            # Check if there is a more specific generator present
            # Otherwise use the default generator
            generator_method_name = "_generate_attribute_default"
            if hasattr(self, f"generate_{attr_schema.name}"):
                generator_method_name = f"generate_{attr_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    attr_schema.name,
                    await generator_method(
                        db=db, name=attr_schema.name, schema=attr_schema, data=fields.get(attr_schema.name, None)
                    ),
                )
                if not self._existing:
                    attribute: BaseAttribute = getattr(self, attr_schema.name)
                    await self.handle_pool(db=db, attribute=attribute, errors=errors)

                    attribute.validate(value=attribute.value, name=attribute.name, schema=attribute.schema)
            except ValidationError as exc:
                errors.append(exc)

        return errors

    async def _process_macros(self, db: InfrahubDatabase) -> None:
        schema_branch = db.schema.get_schema_branch(self._branch.name)
        allowed_path_types = (
            SchemaElementPathType.ATTR_WITH_PROP
            | SchemaElementPathType.REL_ONE_MANDATORY_ATTR_WITH_PROP
            | SchemaElementPathType.REL_ONE_OPTIONAL_ATTR_WITH_PROP
        )
        errors = []
        for macro in self._computed_jinja2_attributes:
            variables = {}
            attr_schema = self._schema.get_attribute(name=macro)
            if not attr_schema.computed_attribute:
                errors.append(
                    ValidationError({macro: f"{macro} is missing computational_logic for macro ({attr_schema.kind})"})
                )
                continue
            if not attr_schema.computed_attribute.jinja2_template:
                errors.append(
                    ValidationError({macro: f"{macro} is missing computational_logic for macro ({attr_schema.kind})"})
                )
                continue

            jinja_template = Jinja2Template(template=attr_schema.computed_attribute.jinja2_template)
            for variable in jinja_template.get_variables():
                attribute_path = schema_branch.validate_schema_path(
                    node_schema=self._schema, path=variable, allowed_path_types=allowed_path_types
                )
                if attribute_path.is_type_relationship:
                    relationship_attribute: RelationshipManager = getattr(
                        self, attribute_path.active_relationship_schema.name
                    )
                    peer = await relationship_attribute.get_peer(db=db, raise_on_error=True)

                    related_node = await registry.manager.get_one_by_id_or_default_filter(
                        db=db, id=peer.id, kind=attribute_path.active_relationship_schema.peer, branch=self._branch.name
                    )

                    attribute: BaseAttribute = getattr(
                        getattr(related_node, attribute_path.active_attribute_schema.name),
                        attribute_path.active_attribute_property_name,
                    )
                    variables[variable] = attribute

                elif attribute_path.is_type_attribute:
                    attribute = getattr(
                        getattr(self, attribute_path.active_attribute_schema.name),
                        attribute_path.active_attribute_property_name,
                    )
                    variables[variable] = attribute

            content = await jinja_template.render(variables=variables)

            generator_method_name = "_generate_attribute_default"
            if hasattr(self, f"generate_{attr_schema.name}"):
                generator_method_name = f"generate_{attr_schema.name}"

            generator_method = getattr(self, generator_method_name)
            try:
                setattr(
                    self,
                    attr_schema.name,
                    await generator_method(db=db, name=attr_schema.name, schema=attr_schema, data=content),
                )
                attribute = getattr(self, attr_schema.name)

                attribute.validate(value=attribute.value, name=attribute.name, schema=attribute.schema)
            except ValidationError as exc:
                errors.append(exc)

        if errors:
            raise ValidationError(errors)

    async def _generate_relationship_default(
        self,
        name: str,  # noqa: ARG002
        schema: RelationshipSchema,
        data: Any,
        db: InfrahubDatabase,
    ) -> RelationshipManager:
        rm = await RelationshipManager.init(
            db=db,
            data=data,
            schema=schema,
            branch=self._branch,
            at=self._at,
            node=self,
        )

        return rm

    async def _generate_attribute_default(
        self,
        name: str,
        schema: AttributeSchema,
        data: Any,
        db: InfrahubDatabase,  # noqa: ARG002
    ) -> BaseAttribute:
        attr_class = ATTRIBUTE_TYPES[schema.kind].get_infrahub_class()
        attr = attr_class(
            data=data,
            name=name,
            schema=schema,
            branch=self._branch,
            at=self._at,
            node=self,
            source=self._source,
            owner=self._owner,
        )
        return attr

    async def process_label(self, db: InfrahubDatabase | None = None) -> None:  # noqa: ARG002
        # If there label and name are both defined for this node
        #  if label is not define, we'll automatically populate it with a human friendy vesion of name
        if not self._existing and hasattr(self, "label") and hasattr(self, "name"):
            if self.label.value is None and self.name.value:
                self.label.value = " ".join([word.title() for word in self.name.value.split("_")])
                self.label.is_default = False

    async def new(self, db: InfrahubDatabase, id: str | None = None, **kwargs: Any) -> Self:
        if id and not is_valid_uuid(id):
            raise ValidationError({"id": f"{id} is not a valid UUID"})
        if id:
            query = await NodeCheckIDQuery.init(db=db, node_id=id)
            if await query.count(db=db):
                raise ValidationError({"id": f"{id} is already in use"})

        self.id = id or str(UUIDT())

        await self._process_fields(db=db, fields=kwargs)
        await self._process_macros(db=db)

        return self

    async def resolve_relationships(self, db: InfrahubDatabase) -> None:
        for name in self._relationships:
            relm: RelationshipManager = getattr(self, name)
            await relm.resolve(db=db)

    async def load(
        self,
        db: InfrahubDatabase,
        id: str | None = None,
        db_id: str | None = None,
        updated_at: Timestamp | str | None = None,
        **kwargs: Any,
    ) -> Self:
        self.id = id
        self.db_id = db_id
        self._existing = True

        if updated_at:
            kwargs["updated_at"] = (
                updated_at  # FIXME: Allow users to use "updated_at" named attributes until we have proper metadata handling
            )
            self._updated_at = Timestamp(updated_at)

        await self._process_fields(db=db, fields=kwargs)
        return self

    async def _create(self, db: InfrahubDatabase, at: Timestamp | None = None) -> NodeChangelog:
        create_at = Timestamp(at)

        query = await NodeCreateAllQuery.init(db=db, node=self, at=create_at)
        await query.execute(db=db)

        _, self.db_id = query.get_self_ids()
        self._at = create_at
        self._updated_at = create_at
        self._existing = True

        new_ids = query.get_ids()
        node_changelog = NodeChangelog(node_id=self.get_id(), node_kind=self.get_kind(), display_label="")

        # Go over the list of Attribute and assign the new IDs one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            attr.id, attr.db_id = new_ids[name]
            attr.at = create_at
            node_changelog.create_attribute(attribute=attr)

        # Go over the list of relationships and assign the new IDs one by one
        for name in self._relationships:
            relm: RelationshipManager = getattr(self, name)
            for rel in relm._relationships:
                identifier = f"{rel.schema.identifier}::{rel.peer_id}"

                rel.id, rel.db_id = new_ids[identifier]

                node_changelog.create_relationship(relationship=rel)

        node_changelog.display_label = await self.render_display_label(db=db)
        return node_changelog

    async def _update(
        self, db: InfrahubDatabase, at: Timestamp | None = None, fields: list[str] | None = None
    ) -> NodeChangelog:
        """Update the node in the database if needed."""

        update_at = Timestamp(at)
        node_changelog = NodeChangelog(node_id=self.get_id(), node_kind=self.get_kind(), display_label="")

        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            if (fields and name in fields) or not fields:
                attr: BaseAttribute = getattr(self, name)
                updated_attribute = await attr.save(at=update_at, db=db)
                if updated_attribute:
                    node_changelog.add_attribute(attribute=updated_attribute)

        # Go over the list of relationships and update them one by one
        processed_relationships: list[str] = []
        for name in self._relationships:
            if (fields and name in fields) or not fields:
                processed_relationships.append(name)
                rel: RelationshipManager = getattr(self, name)
                updated_relationship = await rel.save(at=update_at, db=db)
                node_changelog.add_relationship(relationship_changelog=updated_relationship)

        if len(processed_relationships) != len(self._relationships):
            # Analyze if the node has a parent and add it to the changelog if missing
            if parent_relationship := self._get_parent_relationship_name():
                if parent_relationship not in processed_relationships:
                    rel: RelationshipManager = getattr(self, parent_relationship)
                    if parent := await rel.get_parent(db=db):
                        node_changelog.add_parent_from_relationship(parent=parent)

        node_changelog.display_label = await self.render_display_label(db=db)
        return node_changelog

    async def save(self, db: InfrahubDatabase, at: Timestamp | None = None, fields: list[str] | None = None) -> Self:
        """Create or Update the Node in the database."""

        save_at = Timestamp(at)

        if self._existing:
            self._node_changelog = await self._update(at=save_at, db=db, fields=fields)
            return self

        self._node_changelog = await self._create(at=save_at, db=db)
        return self

    async def delete(self, db: InfrahubDatabase, at: Timestamp | None = None) -> None:
        """Delete the Node in the database."""

        delete_at = Timestamp(at)

        node_changelog = NodeChangelog(
            node_id=self.get_id(), node_kind=self.get_kind(), display_label=await self.render_display_label(db=db)
        )
        # Go over the list of Attribute and update them one by one
        for name in self._attributes:
            attr: BaseAttribute = getattr(self, name)
            deleted_attribute = await attr.delete(at=delete_at, db=db)
            if deleted_attribute:
                node_changelog.add_attribute(attribute=deleted_attribute)

        branch = self.get_branch_based_on_support_type()

        delete_query = await RelationshipDeleteAllQuery.init(
            db=db, node_id=self.get_id(), branch=branch, at=delete_at, branch_agnostic=branch.name == GLOBAL_BRANCH_NAME
        )
        await delete_query.execute(db=db)

        deleted_relationships_changelogs = delete_query.get_deleted_relationships_changelog(self._schema)
        for relationship_changelog in deleted_relationships_changelogs:
            node_changelog.add_relationship(relationship_changelog=relationship_changelog)

        # Update the relationship to the branch itself
        query = await NodeGetListQuery.init(
            db=db,
            schema=self._schema,
            filters={"id": self.id},
            branch=self._branch,
            at=delete_at,
            order=OrderModel(disable=True),
        )
        await query.execute(db=db)
        result = query.get_result()

        if result and result.get("rb.branch") == branch.name:
            await update_relationships_to([result.get("rb_id")], to=delete_at, db=db)

        query = await NodeDeleteQuery.init(db=db, node=self, at=delete_at)
        await query.execute(db=db)
        self._node_changelog = node_changelog

    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: dict | None = None,
        related_node_ids: set | None = None,
        filter_sensitive: bool = False,
        permissions: dict | None = None,
        include_properties: bool = True,
    ) -> dict:
        """Generate GraphQL Payload for all attributes

        Returns:
            (dict): Return GraphQL Payload
        """

        response: dict[str, Any] = {"id": self.id, KIND_GRAPHQL_FIELD_NAME: self.get_kind()}

        if related_node_ids is not None:
            related_node_ids.add(self.id)

        FIELD_NAME_TO_EXCLUDE = ["id"] + self._schema.relationship_names

        if fields and isinstance(fields, dict):
            field_names = [field_name for field_name in fields.keys() if field_name not in FIELD_NAME_TO_EXCLUDE]
        else:
            field_names = self._schema.attribute_names + ["__typename", "display_label"]

        for field_name in field_names:
            if field_name == "__typename":
                # Note we already store kind within KIND_GRAPHQL_FIELD_NAME.
                response[field_name] = self.get_kind()
                continue

            if field_name == "display_label":
                response[field_name] = await self.render_display_label(db=db)
                continue

            if field_name == "hfid":
                response[field_name] = await self.get_hfid(db=db)
                continue

            if field_name == "_updated_at":
                if self._updated_at:
                    response[field_name] = await self._updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            field: BaseAttribute | None = getattr(self, field_name, None)

            if not field:
                response[field_name] = None
                continue

            if fields and isinstance(fields, dict):
                response[field_name] = await field.to_graphql(
                    db=db,
                    fields=fields.get(field_name),
                    related_node_ids=related_node_ids,
                    filter_sensitive=filter_sensitive,
                    permissions=permissions,
                    include_properties=include_properties,
                )
            else:
                response[field_name] = await field.to_graphql(
                    db=db,
                    filter_sensitive=filter_sensitive,
                    permissions=permissions,
                    include_properties=include_properties,
                )

        for relationship_schema in self.get_schema().relationships:
            peer_rels = []
            if not fields or relationship_schema.name not in fields:
                continue
            rel_manager = getattr(self, relationship_schema.name, None)
            if rel_manager is None:
                continue
            try:
                if relationship_schema.cardinality is RelationshipCardinality.ONE:
                    rel = rel_manager.get_one()
                    if rel:
                        peer_rels = [rel]
                else:
                    peer_rels = list(rel_manager)
                if peer_rels:
                    response[relationship_schema.name] = [
                        {"node": {"id": relationship.peer_id}} for relationship in peer_rels if relationship.peer_id
                    ]
            except LookupError:
                continue

        return response

    async def from_graphql(self, data: dict, db: InfrahubDatabase) -> bool:
        """Update object from a GraphQL payload."""

        changed = False

        for key, value in data.items():
            if key in self._attributes and isinstance(value, dict):
                attribute = getattr(self, key)
                changed |= await attribute.from_graphql(data=value, db=db)

            if key in self._relationships:
                rel: RelationshipManager = getattr(self, key)
                changed |= await rel.update(db=db, data=value)

        return changed

    async def render_display_label(self, db: InfrahubDatabase | None = None) -> str:  # noqa: ARG002
        if not self._schema.display_labels:
            return repr(self)

        display_elements = []
        for item in self._schema.display_labels:
            item_elements = item.split("__")
            if len(item_elements) != 2:
                raise ValidationError("Display Label can only have one level")

            if item_elements[0] not in self._schema.attribute_names:
                raise ValidationError("Only Attribute can be used in Display Label")

            attr = getattr(self, item_elements[0])
            attr_value = getattr(attr, item_elements[1])
            if isinstance(attr_value, Enum):
                display_elements.append(attr_value.value)
            else:
                display_elements.append(attr_value)

        if not display_elements or all(de is None for de in display_elements):
            return ""
        display_label = " ".join([str(de) for de in display_elements])
        if not display_label.strip():
            return repr(self)
        return display_label.strip()

    def _get_parent_relationship_name(self) -> str | None:
        """Return the name of the parent relationship is one is present"""
        for relationship in self._schema.relationships:
            if relationship.kind == RelationshipKind.PARENT:
                return relationship.name

    async def get_object_template(self, db: InfrahubDatabase) -> CoreObjectTemplate | None:
        object_template: RelationshipManager = getattr(self, OBJECT_TEMPLATE_RELATIONSHIP_NAME, None)
        return (
            await object_template.get_peer(db=db, peer_type=CoreObjectTemplate) if object_template is not None else None
        )

    def get_relationships(
        self, kind: RelationshipKind, exclude: Sequence[str] | None = None
    ) -> list[RelationshipSchema]:
        """Return relationships of a given kind with the possiblity to exclude some of them by name."""
        if exclude is None:
            exclude = []

        return [
            relationship
            for relationship in self.get_schema().relationships
            if relationship.name not in exclude and relationship.kind == kind
        ]

    def validate_relationships(self) -> None:
        for name in self._relationships:
            relm: RelationshipManager = getattr(self, name)
            relm.validate()
