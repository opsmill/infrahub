import uuid
from typing import List, Optional

from pydantic import BaseModel

from infrahub.database import execute_read_query, execute_write_query


class StandardNode(BaseModel):

    id: Optional[int]
    uuid: Optional[str]

    # owner: Optional[str]

    _exclude_attrs: List[str] = ["id", "uuid", "owner"]

    @classmethod
    def get_type(cls):
        return cls.__name__

    def to_graphql(self, fields=None):

        response = {"id": self.uuid}

        for field_name in fields.keys():
            if field_name in ["id"]:
                continue
            field = getattr(self, field_name)
            if not field:
                response[field_name] = None
                continue
            response[field_name] = field

        return response

    def save(self):
        """Create or Update the Node in the database."""

        if self.id:
            return self._update()

        return self._create()

    def refresh(self, at=None, branch="main"):
        """Pull the latest state of the object from the database."""

        # Might need ot check how to manage the default value
        raw_attrs = self._get_item_raw(self.id, at=at, branch=branch)
        for item in raw_attrs:
            if item[1] != getattr(self, item[0]):
                setattr(self, item[0], item[1])

        return True

    def _create(self, id=None, branch="main"):
        """Create a new node in the database."""

        node_type = self.get_type()

        attrs = []
        for attr_name, attr in self.__fields__.items():
            if attr_name in self._exclude_attrs:
                continue
            attrs.append(f"{attr_name}: '{getattr(self, attr_name)}'")

        query = """
        CREATE (n:%s { uuid: $uuid, %s })
        RETURN n
        """ % (
            node_type,
            ", ".join(attrs),
        )

        params = {"uuid": str(uuid.uuid4())}

        results = execute_write_query(query, params)
        if not results:
            raise Exception("Unexpected error, unable to create the new node.")

        node = results[0].values()[0]

        self.id = int(node.id)
        self.uuid = node["uuid"]

        return True

    def _update(self):
        """Update the node in the database if needed."""

        attrs = []
        for attr_name, attr in self.__fields__.items():
            if attr_name in self._exclude_attrs and attr_name != "uuid":
                continue
            attrs.append(f"{attr_name}: '{getattr(self, attr_name)}'")

        query = """
        MATCH (n:%s)
        WHERE ID(n) = $node_id
        SET n = { %s }
        RETURN n
        """ % (
            self.get_type(),
            ",".join(attrs),
        )

        params = {"node_id": self.id}

        results = execute_write_query(query, params)

        if not results:
            raise Exception(f"Unexpected error, unable to update the node {self.id} / {self.uuid}.")

        results[0].values()[0]

        return True

    @classmethod
    def get(cls, id):
        """Get a node from the database identied by its ID."""

        node = cls._get_item_raw(id=id)
        if node:
            return cls._convert_node_to_obj(node)

        return None

    @classmethod
    def _get_item_raw(cls, id):

        query = (
            """
        MATCH (n:%s)
        WHERE ID(n) = $node_id OR n.uuid = $node_id
        RETURN n
        """
            % cls.get_type()
        )

        params = {"node_id": id}

        results = execute_read_query(query, params)
        if len(results):
            return results[0].values()[0]

    @classmethod
    def _convert_node_to_obj(cls, node):
        """Convert a Neo4j Node to a Infrahub StandardNode

        Args:
            node (neo4j.graph.Node): Neo4j Node object

        Returns:
            StandardNode: Proper StandardNode object
        """
        attrs = dict(node)
        attrs["id"] = node.id
        return cls(**attrs)

    @classmethod
    def get_list(cls, limit=1000):

        query = (
            """
        MATCH (n:%s)
        RETURN n
        ORDER BY ID(n)
        LIMIT $limit
        """
            % cls.get_type()
        )

        params = {"limit": 1000}

        results = execute_read_query(query, params)
        return [cls._convert_node_to_obj(node.values()[0]) for node in results]
