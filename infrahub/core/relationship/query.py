from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.schema import RelationshipSchema


class RelationshipQuery(Query):
    def __init__(self, source, destination, rel, *args, **kwargs):
        self.source = source
        self.destination = destination
        self.rel = rel

        super().__init__(*args, **kwargs)


class RelationshipCreateQuery(RelationshipQuery):
    name = "relationship_create"

    type: QueryType = QueryType.WRITE

    def query_init(self):

        # FIXME DO we need to check if both nodes are part of the same Branch right now ?

        self.params["source_id"] = self.source.db_id
        self.params["destination_id"] = self.destination.db_id
        self.params["name"] = self.rel.schema.identifier

        self.params["uuid"] = str(uuid.uuid4())

        self.params["branch"] = self.rel.branch.name

        query = """
        MATCH (s) WHERE ID(s) = $source_id
        MATCH (d) WHERE ID(d) = $destination_id
        CREATE (rl:Relationship { uuid: $uuid, name: $name})
        CREATE (s)-[r1:%s { branch: $branch, status: "active", from: $at, to: null }]->(rl)
        CREATE (d)-[r2:%s { branch: $branch, status: "active", from: $at, to: null  }]->(rl)
        """ % (
            self.rel.rel_type,
            self.rel.rel_type,
        )

        at = self.at or self.rel.at
        self.params["at"] = at.to_string()

        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl", "r1", "r2"]


class RelationshipDeleteQuery(RelationshipQuery):
    name = "relationship_delete"

    type: QueryType = QueryType.WRITE

    def query_init(self):

        # FIXME DO we need to check if both nodes are part of the same Branch right now ?

        self.params["source_id"] = self.source.db_id
        self.params["destination_id"] = self.destination.db_id
        self.params["name"] = self.rel.schema.identifier

        self.params["uuid"] = self.rel.id

        self.params["branch"] = self.rel.branch.name

        query = """
        MATCH (s) WHERE ID(s) = $source_id
        MATCH (d) WHERE ID(d) = $destination_id
        MERGE (rl:Relationship { uuid: $uuid, name: $name})
        CREATE (s)-[r1:%s { branch: $branch, status: "deleted", from: $at, to: null }]->(rl)
        CREATE (d)-[r2:%s { branch: $branch, status: "deleted", from: $at, to: null  }]->(rl)
        """ % (
            self.rel.rel_type,
            self.rel.rel_type,
        )

        at = self.at or self.rel.at
        self.params["at"] = at.to_string()

        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl", "r1", "r2"]


class RelationshipGetPeerQuery(Query):
    name = "relationship_get_peer"

    type: QueryType = QueryType.READ

    def __init__(
        self,
        source_id: str,
        schema: RelationshipSchema,
        filters: dict = None,
        limit: int = None,
        rel_type: str = None,
        *args,
        **kwargs,
    ):

        self.source_id = source_id
        self.schema = schema
        self.rel_type = rel_type
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

        # import pdb
        # pdb.set_trace()
        # query = """
        # MATCH (s { uuid: $source_id })
        # MATCH (s)-[r1]->(rl:Relationship { name: $identifier })<-[r2]-(d)
        # WHERE %s
        # """ % (
        #     "\n AND ".join(
        #         rels_filter,
        #     ),
        # )

        # self.add_to_query(query)
        # self.return_labels = ["s", "d", "rl"] + [f"r{i}" for i in range(1, nbr_rels+1)]

        # if self.filters:

        #     clean_filters = {
        #         key.replace(f"{self.schema.name}__", ""): value
        #         for key, value in self.filters.items()
        #         if key.startswith(f"{self.schema.name}__")
        #     }

        #     peer_filters, peer_params, nbr_rels = self.schema.get_query_filter(filters=clean_filters, branch=self.branch, rels_offset=2)
        #     self.params.update(peer_params)

        #     self.add_to_query(
        #         "WITH " + ",".join(self.return_labels)
        #     )  # [label for label in self.return_labels if not label.startswith("r")]))

        #     for field_filter in peer_filters:
        #         self.add_to_query(field_filter)

        # if Filters are provided
        # Remove the first part of the query that identify the field
        # { "name__name": value }

        # for field_name in self.peer_schema.valid_input_names:

        #     attr_filters = {
        #         key.replace(f"{self.schema.name}__{field_name}__", ""): value
        #         for key, value in self.filters.items()
        #         if key.startswith(f"{self.schema.name}__{field_name}__")
        #     }

        #     field = self.peer_schema.get_field(field_name)

        # field_filters, field_params, nbr_rels = field.get_query_filter(
        #     name=field_name, filters=attr_filters, branch=self.branch
        # )
        # self.params.update(field_params)

        # self.add_to_query(
        #     "WITH " + ",".join(self.return_labels)
        # )  # [label for label in self.return_labels if not label.startswith("r")]))

        # for field_filter in field_filters:
        #     self.add_to_query(field_filter)

        # rels_filter, rels_params = self.branch.get_query_filter_relationships(
        #     rel_labels=[f"r{y+1}" for y in range(nbr_rels)],
        #     at=self.at.to_string(),
        #     include_outside_parentheses=True,
        # )
        # self.params.update(rels_params)
        # self.add_to_query("WHERE " + "\n AND ".join(rels_filter))

    def get_peer_ids(self) -> List[str]:
        """Return a list of UUID of nodes associated with this relationship."""

        if self.num_of_results == 0:
            return None

        return [result.get("p").get("uuid") for result in self.get_results_group_by(("p", "uuid"))]


class RelationshipGetQuery(RelationshipQuery):
    name = "relationship_get"

    type: QueryType = QueryType.READ

    def query_init(self):

        self.params["source_id"] = self.source.db_id
        self.params["destination_id"] = self.destination.db_id
        self.params["name"] = self.rel.schema.identifier
        self.params["branch"] = self.branch.name

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at.to_string(), include_outside_parentheses=True
        )

        self.params.update(rels_params)

        query = """
        MATCH (s) WHERE ID(s) = $source_id
        MATCH (d) WHERE ID(d) = $destination_id
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
