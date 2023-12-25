from infrahub.core.node.standard import StandardNode
from infrahub.core.query.standard_node import RootNodeCreateQuery
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import Error


class Root(StandardNode):
    async def create(self, db: InfrahubDatabase) -> bool:
        """Create a new node in the database."""

        query = await RootNodeCreateQuery.init(db=db, node=self)
        await query.execute(db=db)

        result = query.get_result()
        if not result:
            raise Error("Unable to create the Root node")
        node = result.get("n")

        self.id = node.element_id
        self.uuid = node["uuid"]

        return True
