import ipaddress

from infrahub.core import registry
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def reconciliation(message: messages.TriggerIpamReconciliation, service: InfrahubServices) -> None:
    branch = await registry.get_branch(db=service.database, branch=message.branch)
    ipam_reconciler = IpamReconciler(db=service.database, branch=branch)

    for ipam_node_details in message.ipam_node_details:
        if ipam_node_details.is_address:
            ip_value = ipaddress.ip_interface(ipam_node_details.ip_value)
        else:
            ip_value = ipaddress.ip_network(ipam_node_details.ip_value)
        await ipam_reconciler.reconcile(
            ip_value=ip_value, namespace=ipam_node_details.namespace_id, node_uuid=ipam_node_details.node_uuid
        )
