from __future__ import annotations
from collections import defaultdict

import inspect
from dataclasses import dataclass

from uuid import UUID, uuid4
from typing import Union, Type, List, Dict, Generator, TYPE_CHECKING

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.relationship import Relationship
    from infrahub.core.node import Node
    from infrahub.core.schema import RelationshipSchema
    from infrahub.core.branch import Branch


@dataclass
class RelData:
    """Represent a relationship object in the database."""

    db_id: int
    branch: str
    type: str
    status: str

    @classmethod
    def from_db(cls, obj):
        return cls(db_id=obj.id, branch=obj.get("branch"), type=obj.type, status=obj.get("status"))


@dataclass
class FlagPropertyData:
    name: str
    prop_db_id: int
    rel: RelData
    value: bool


@dataclass
class NodePropertyData:
    name: str
    prop_db_id: int
    rel: RelData
    value: UUID


@dataclass
class RelationshipPeerData:

    branch: str

    peer_id: UUID
    """UUID of the Peer Node."""

    properties: Dict[str, Union[FlagPropertyData, NodePropertyData]]
    """UUID of the Relationship Node."""

    rel_node_id: UUID = None
    """UUID of the Relationship Node."""

    peer_db_id: int = None
    """Internal DB ID of the Peer Node."""

    rel_node_db_id: int = None
    """Internal DB ID of the Relationship Node."""

    rels: List[RelData] = None
    """Both relationships pointing at this Relationship Node."""

    updated_at: str = None

    def rel_ids_per_branch(self):

        response = defaultdict(list)
        for rel in self.rels:
            response[rel.branch].append(rel.db_id)

        for prop in self.properties.values():
            response[prop.rel.branch].append(prop.rel.db_id)

        return response


class RelationshipQuery(Query):
    def __init__(
        self,
        rel: Union[Type[Relationship], Relationship] = None,
        rel_type: str = None,
        source: Node = None,
        source_id: UUID = None,
        destination: Node = None,
        destination_id: UUID = None,
        schema: RelationshipSchema = None,
        branch: Branch = None,
        at: Union[Timestamp, str] = None,
        *args,
        **kwargs,
    ):

        if not source and not source_id:
            raise ValueError("Either source or source_id must be provided.")
        if not rel and not rel_type:
            raise ValueError("Either rel or rel_type must be provided.")
        if not inspect.isclass(rel) and not hasattr(rel, "schema"):
            raise ValueError("Rel must be a Relationship class or an instance of Relationship.")
        if not schema and inspect.isclass(rel) and not hasattr(rel, "schema"):
            raise ValueError("Either an instance of Relationship or a valid schema must be provided.")

        self.source_id = source_id or source.id
        self.source = source

        # Destination is optional because not all RelationshipQuery needs it
        # If a query must have a destination defined, the validation must be done in the query specific init
        self.destination = destination
        self.destination_id = destination_id
        if not self.destination_id and destination:
            self.destination_id = destination.id

        self.rel = rel
        self.rel_type = rel_type or self.rel.rel_type
        self.schema = schema or self.rel.schema

        if not branch and inspect.isclass(rel) and not hasattr(rel, "branch"):
            raise ValueError("Either an instance of Relationship or a valid branch must be provided.")

        self.branch = branch or self.rel.branch

        if at:
            self.at = Timestamp(at)
        elif inspect.isclass(rel) and hasattr(rel, "at"):
            self.at = self.rel.at
        else:
            self.at = Timestamp()

        super().__init__(*args, **kwargs)


class RelationshipCreateQuery(RelationshipQuery):
    name = "relationship_create"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        destination: Node = None,
        destination_id: UUID = None,
        *args,
        **kwargs,
    ):

        if not destination and not destination_id:
            raise ValueError("Either destination or destination_id must be provided.")

        super().__init__(destination=destination, destination_id=destination_id, *args, **kwargs)

    def query_init(self):

        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.destination_id
        self.params["name"] = self.schema.identifier

        self.params["uuid"] = str(uuid4())

        self.params["branch"] = self.branch.name
        self.params["at"] = self.at.to_string()

        self.params["is_protected"] = self.rel.is_protected
        self.params["is_visible"] = self.rel.is_visible

        query_match = """
        MATCH (s { uuid: $source_id })
        MATCH (d { uuid: $destination_id })
        """
        self.add_to_query(query_match)

        self.query_add_all_node_property_match()

        query_create = """
        CREATE (rl:Relationship { uuid: $uuid, name: $name})
        CREATE (s)-[r1:%s { branch: $branch, status: "active", from: $at, to: null }]->(rl)
        CREATE (d)-[r2:%s { branch: $branch, status: "active", from: $at, to: null  }]->(rl)
        MERGE (ip:Boolean { value: $is_protected })
        MERGE (iv:Boolean { value: $is_visible })
        CREATE (rl)-[r3:IS_PROTECTED { branch: $branch, status: "active", from: $at, to: null }]->(ip)
        CREATE (rl)-[r4:IS_VISIBLE { branch: $branch, status: "active", from: $at, to: null }]->(iv)
        """ % (
            self.rel_type,
            self.rel_type,
        )

        self.add_to_query(query_create)
        self.return_labels = ["s", "d", "rl", "r1", "r2", "r3", "r4"]
        self.query_add_all_node_property_create()

    def query_add_all_node_property_match(self):
        for prop_name in self.rel._node_properties:
            if hasattr(self.rel, f"{prop_name}_id") and getattr(self.rel, f"{prop_name}_id"):
                self.query_add_node_property_match(name=prop_name)

    def query_add_node_property_match(self, name: str):
        self.add_to_query("MATCH (%s { uuid: $prop_%s_id })" % (name, name))
        self.params[f"prop_{name}_id"] = getattr(self.rel, f"{name}_id")
        self.return_labels.append(name)

    def query_add_all_node_property_create(self):
        for prop_name in self.rel._node_properties:
            if hasattr(self.rel, f"{prop_name}_id") and getattr(self.rel, f"{prop_name}_id"):
                self.query_add_node_property_create(name=prop_name)

    def query_add_node_property_create(self, name: str):
        query = """
        CREATE (rl)-[:HAS_%s { branch: $branch, status: "active", from: $at, to: null }]->(%s)
        """ % (
            name.upper(),
            name,
        )
        self.add_to_query(query)


class RelationshipUpdatePropertyQuery(RelationshipQuery):
    name = "relationship_property_update"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        properties_to_update: List[str],
        data: RelationshipPeerData,
        *args,
        **kwargs,
    ):

        self.properties_to_update = properties_to_update
        self.data = data

        super().__init__(*args, **kwargs)

    def query_init(self):

        self.params["rel_node_id"] = self.data.rel_node_id
        self.params["branch"] = self.branch.name
        self.params["at"] = self.at.to_string()

        query = """
        MATCH (rl { uuid: $rel_node_id })
        """
        self.add_to_query(query)

        self.query_add_all_flag_property_merge()

        self.query_add_all_flag_property_create()

    def query_add_all_flag_property_merge(self):
        for prop_name in self.rel._flag_properties:
            if prop_name in self.properties_to_update:
                self.query_add_flag_property_merge(name=prop_name)

    def query_add_flag_property_merge(self, name: str):
        self.add_to_query("MERGE (prop_%s:Boolean { value: $prop_%s })" % (name, name))
        self.params[f"prop_{name}"] = getattr(self.rel, name)
        self.return_labels.append(f"prop_{name}")

    def query_add_all_flag_property_create(self):
        for prop_name in self.rel._flag_properties:
            if prop_name in self.properties_to_update:
                self.query_add_flag_property_create(name=prop_name)

    def query_add_flag_property_create(self, name: str):
        query = """
        CREATE (rl)-[:%s { branch: $branch, status: "active", from: $at, to: null }]->(prop_%s)
        """ % (
            name.upper(),
            name,
        )
        self.add_to_query(query)


class RelationshipDataDeleteQuery(RelationshipQuery):
    name = "relationship_data_delete"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        data: RelationshipPeerData,
        *args,
        **kwargs,
    ):

        self.data = data
        super().__init__(*args, **kwargs)

    def query_init(self):

        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.data.peer_id
        self.params["rel_node_id"] = self.data.rel_node_id
        self.params["name"] = self.schema.identifier
        self.params["branch"] = self.branch.name
        self.params["at"] = self.at.to_string()

        # -----------------------------------------------------------------------
        # Match all nodes, including properties
        # -----------------------------------------------------------------------
        query = """
        MATCH (s { uuid: $source_id })
        MATCH (d { uuid: $destination_id })
        MATCH (rl { uuid: $rel_node_id })
        """
        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl"]

        for prop_name, prop in self.data.properties.items():
            self.add_to_query("MATCH (prop_%s) WHERE ID(prop_%s) = $prop_%s_id" % (prop_name, prop_name, prop_name))
            self.params[f"prop_{prop_name}_id"] = prop.prop_db_id
            self.return_labels.append(f"prop_{prop_name}")

        # -----------------------------------------------------------------------
        # Create all the DELETE relationships, including properties
        # -----------------------------------------------------------------------
        query = """
        CREATE (s)-[r1:%s { branch: $branch, status: "deleted", from: $at, to: null }]->(rl)
        CREATE (d)-[r2:%s { branch: $branch, status: "deleted", from: $at, to: null  }]->(rl)
        """ % (
            self.rel_type,
            self.rel_type,
        )
        self.add_to_query(query)
        self.return_labels.extend(["r1", "r2"])

        for prop_name, prop in self.data.properties.items():
            self.add_to_query(
                'CREATE (prop_%s)-[rel_prop_%s:%s { branch: $branch, status: "deleted", from: $at, to: null  }]->(rl)'
                % (prop_name, prop_name, prop_name.upper()),
            )
            self.return_labels.append(f"rel_prop_{prop_name}")


class RelationshipDeleteQuery(RelationshipQuery):
    name = "relationship_delete"

    type: QueryType = QueryType.WRITE

    def query_init(self):

        # FIXME DO we need to check if both nodes are part of the same Branch right now ?

        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.destination_id
        self.params["name"] = self.schema.identifier
        self.params["branch"] = self.branch.name

        query = """
        MATCH (s { uuid: $source_id })-[]-(rl:Relationship {name: $name})-[]-(d { uuid: $destination_id })
        CREATE (s)-[r1:%s { branch: $branch, status: "deleted", from: $at, to: null }]->(rl)
        CREATE (d)-[r2:%s { branch: $branch, status: "deleted", from: $at, to: null  }]->(rl)
        """ % (
            self.rel_type,
            self.rel_type,
        )

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl", "r1", "r2"]


class RelationshipGetPeerQuery(RelationshipQuery):
    name = "relationship_get_peer"

    type: QueryType = QueryType.READ

    def __init__(
        self,
        filters: dict = None,
        limit: int = None,
        *args,
        **kwargs,
    ):

        self.filters = filters or {}
        self.limit = limit

        super().__init__(*args, **kwargs)

    def query_init(self):

        self.params["source_id"] = self.source_id

        query = "MATCH (n { uuid: $source_id })"
        self.add_to_query(query)

        clean_filters = {
            key.replace(f"{self.schema.name}__", ""): value
            for key, value in self.filters.items()
            if key.startswith(f"{self.schema.name}__")
        }

        if clean_filters:
            peer_filters, peer_params, nbr_rels = self.schema.get_query_filter(
                filters=clean_filters, branch=self.branch, rels_offset=0
            )
            self.params.update(peer_params)

            for field_filter in peer_filters:
                self.add_to_query(field_filter)

            rels_filter, rels_params = self.branch.get_query_filter_relationships(
                rel_labels=[f"r{i}" for i in range(1, nbr_rels + 1)],
                at=self.at.to_string(),
                include_outside_parentheses=True,
            )

            self.params.update(rels_params)

            query = "WHERE " + "\n AND ".join(rels_filter)
            self.add_to_query(query)

            self.return_labels = ["n", "p", "rl"] + [f"r{i}" for i in range(1, nbr_rels + 1)]

        else:

            self.params["identifier"] = self.schema.identifier

            rels_filter, rels_params = self.branch.get_query_filter_relationships(
                rel_labels=["r1", "r2"], at=self.at.to_string(), include_outside_parentheses=True
            )
            self.params.update(rels_params)

            query = """
            MATCH (n)-[r1]->(rl:Relationship { name: $identifier })<-[r2]-(p)
            WHERE %s
            """ % (
                "\n AND ".join(
                    rels_filter,
                ),
            )
            self.add_to_query(query)

            self.return_labels = ["n", "p", "rl", "r1", "r2"]

        # Add Flag Properties
        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["rel_is_visible", "rel_is_protected"], at=self.at.to_string(), include_outside_parentheses=True
        )
        self.params.update(rels_params)

        query = """
        WITH %s
        MATCH (rl)-[rel_is_visible:IS_VISIBLE]-(is_visible)
        MATCH (rl)-[rel_is_protected:IS_PROTECTED]-(is_protected)
        WHERE %s
        """ % (
            ",".join(self.return_labels),
            "\n AND ".join(
                rels_filter,
            ),
        )
        self.add_to_query(query)
        self.return_labels.extend(["rel_is_visible", "rel_is_protected", "is_visible", "is_protected"])

        ## Add Node Properties

        # ## FIXME, make this part dynamic to generate the query based on the list of supported properties
        # rels_filter, rels_params = self.branch.get_query_filter_relationships(
        #     rel_labels=["rel_source", "rel_owner"], at=self.at.to_string(), include_outside_parentheses=True
        # )
        # self.params.update(rels_params)

        # query = """
        # WITH %s
        # MATCH OPTIONAL (rl)-[rel_source:HAS_SOURCE]-(source)
        # MATCH OPTIONAL (rl)-[rel_owner:HAS_OWNER]-(owner)
        # WHERE %s
        # """ % (",".join(self.return_labels), "\n AND ".join(
        #             rels_filter,
        #         ))
        # self.return_labels.extend(["rel_source", "rel_owner", "source", "owner"])

    def get_peer_ids(self) -> List[str]:
        """Return a list of UUID of nodes associated with this relationship."""

        return [peer.peer_id for peer in self.get_peers()]

    def get_peers(self) -> Generator[RelationshipPeerData, None, None]:

        for result in self.get_results_group_by(("p", "uuid")):
            data = RelationshipPeerData(
                peer_id=result.get("p").get("uuid"),
                rel_node_db_id=result.get("rl").id,
                rel_node_id=result.get("rl").get("uuid"),
                updated_at=result.get("r1").get("from"),
                rels=[RelData.from_db(result.get("r1")), RelData.from_db(result.get("r2"))],
                branch=self.branch,
                properties=dict(),
            )

            if hasattr(self.rel, "_flag_properties"):
                for prop in self.rel._flag_properties:

                    if prop_node := result.get(prop):
                        data.properties[prop] = FlagPropertyData(
                            name=prop,
                            prop_db_id=prop_node.id,
                            rel=RelData.from_db(result.get(f"rel_{prop}")),
                            value=prop_node.get("value"),
                        )

            # if hasattr(self.rel, "_node_properties"):
            #     for prop in self.rel._node_properties:

            #         if prop_node := result.get(prop):
            #             data.properties[prop] = NodePropertyData(
            #                 name=prop,
            #                 prop_db_id=prop_node.id,
            #                 rel==RelData.from_db(result.get(f"rel_{prop}")),
            #             )

            yield data


class RelationshipGetQuery(RelationshipQuery):
    name = "relationship_get"

    type: QueryType = QueryType.READ

    def query_init(self):

        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.destination_id
        self.params["name"] = self.schema.identifier
        self.params["branch"] = self.branch.name

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at.to_string(), include_outside_parentheses=True
        )

        self.params.update(rels_params)

        query = """
        MATCH (s { uuid: $source_id })
        MATCH (d { uuid: $destination_id })
        MATCH (s)-[r1:%s]->(rl:Relationship { name: $name })<-[r2:%s]-(d)
        WHERE %s
        """ % (
            self.rel.rel_type,
            self.rel.rel_type,
            "\n AND ".join(rels_filter),
        )

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl", "r1", "r2"]


class RelationshipListGetPropertiesQuery(Query):
    name = "relationship_list_get_properties"

    type: QueryType = QueryType.READ

    def __init__(
        self,
        ids: List[str],
        account=None,
        *args,
        **kwargs,
    ):
        self.account = account
        self.ids = ids

        super().__init__(*args, **kwargs)

    def query_init(self):

        self.params["branch"] = self.branch.name
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r"], at=self.at.to_string(), include_outside_parentheses=True
        )

        self.params.update(rels_params)

        # TODO Compute the list of potential relationship dynamically in the future based on the class
        query = """
        MATCH (rl) WHERE rl.uuid IN $ids
        MATCH (rl)-[r:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-(rp)
        WHERE %s
        """ % (
            "\n AND ".join(rels_filter),
        )

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["rl", "rp", "r"]

    def get_by_id_and_prop_type(self, rel_id: str, type: str):

        for result in self.get_results_group_by(("rl", "uuid"), ("r", "type")):
            if result.get("rl").get("uuid") == rel_id and result.get("r").type == type:
                return result

        return None
