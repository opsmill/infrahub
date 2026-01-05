from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Sequence

from infrahub.core.branch.models import Branch
from infrahub.core.initialization import initialization
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.timestamp import Timestamp
from infrahub.lock import initialize_lock
from infrahub.log import get_logger

from ..shared import InternalSchemaMigration, SchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration038(InternalSchemaMigration):
    """
    Re-run migration 026 after Migration037 updates AttributeValueIndexed vertices correctly so that the call to
    NodeManager.query will work

    If someone is upgrading from 1.2.4 (release before migration 026) or earlier to 1.4.x or later, then migration 026
    fail to find any 0.0.0.0 prefix nodes even if they exist. So we run it again here after migration 037 makes the
    AttributeValueIndexed changes to be sure it completes correctly.
    """

    name: str = "038_prefix_0000_fix"
    minimum_version: int = 37
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        at = Timestamp()
        for branch in await Branch.get_list(db=db):
            prefix_0000s = await NodeManager.query(
                db=db, schema="BuiltinIPPrefix", branch=branch, filters={"prefix__values": ["0.0.0.0/0", "::/0"]}
            )
            if not prefix_0000s:
                continue
            ipam_reconciler = IpamReconciler(db=db, branch=branch)
            for prefix in prefix_0000s:
                ip_namespace = await prefix.ip_namespace.get_peer(db=db)
                ip_network = ipaddress.ip_network(prefix.prefix.value)
                await ipam_reconciler.reconcile(
                    ip_value=ip_network,
                    namespace=ip_namespace,
                    node_uuid=prefix.get_id(),
                    at=at,
                )

        return MigrationResult()
