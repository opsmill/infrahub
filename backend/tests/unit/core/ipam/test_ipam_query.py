import ipaddress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_ipam_namespace, get_default_ipnamespace
from infrahub.core.query.ipam import IPPrefixReconcileQuery
from infrahub.database import InfrahubDatabase


async def test_ipprefix_reconcile(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    prefix_140 = ip_dataset_01["net140"]
    namespace = ip_dataset_01["ns1"]
    ip_network = ipaddress.ip_network(prefix_140.prefix.value)

    query = await IPPrefixReconcileQuery.init(db=db, branch=default_branch, ip_prefix=ip_network, namespace=namespace)
    await query.execute(db=db)

    assert query.get_current_parent_uuid() == ip_dataset_01["net146"].id
    assert set(query.get_current_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
    }
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net146"].id
    assert set(query.get_calculated_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
    }
