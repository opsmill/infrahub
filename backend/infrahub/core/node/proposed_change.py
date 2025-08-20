from typing import cast

from infrahub.core.constants.infrahubkind import THREADCOMMENT
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange as CoreProposedChangeProtocol
from infrahub.database import InfrahubDatabase


class CoreProposedChange(Node):
    async def to_graphql(
        self,
        db: InfrahubDatabase,
        fields: dict | None = None,
        related_node_ids: set | None = None,
        filter_sensitive: bool = False,
        permissions: dict | None = None,
        include_properties: bool = True,
    ) -> dict:
        response = await super().to_graphql(
            db,
            fields=fields,
            related_node_ids=related_node_ids,
            filter_sensitive=filter_sensitive,
            permissions=permissions,
            include_properties=include_properties,
        )

        if fields:
            if "total_comments" in fields:
                total_comments = 0
                proposed_change = cast(CoreProposedChangeProtocol, self)
                change_comments = await proposed_change.comments.get_relationships(db=db)
                total_comments += len(change_comments)

                threads = await proposed_change.threads.get_peers(db=db)
                thread_comments = await NodeManager.query(
                    db=db, schema=THREADCOMMENT, filters={"thread__ids": list(threads.keys())}
                )
                total_comments += len(thread_comments)
                response["total_comments"] = {"value": total_comments}

        return response
