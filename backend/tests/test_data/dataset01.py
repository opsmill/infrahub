from infrahub.core.node import Node
from infrahub.core.protocols import CoreGroup
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

# pylint: skip-file

ROLES = ["spine", "leaf", "firewall", "server", "loopback"]
STATUSES = ["active", "provisioning", "maintenance"]
TAGS = ["blue", "green", "red"]

DEVICES = (
    ("spine1", "active", "MX480", "profile1", "spine", ["red", "green"]),
    ("spine2", "active", "MX480", "profile1", "spine", ["red", "blue", "green"]),
    ("leaf1", "active", "QFX5100", None, "leaf", ["red", "blue"]),
    ("leaf2", "maintenance", "QFX5100", "profile2", None, ["red", "blue", "green"]),
    ("leaf3", "active", "QFX5100", None, "leaf", ["blue", "green"]),
    ("web01", "active", "s-1vcpu-1gb-intel", None, "server", ["green"]),
    ("web02", "active", "s-1vcpu-1gb-intel", None, "server", ["green", "red"]),
    ("database01", "active", "s-1vcpu-1gb-intel", None, "server", ["green"]),
)

# DEVICE_PROFILES = (
#     ("profile1", "provisioning", "MX240", "spine"),
#     ("profile2", "provisioning", "QFX5200", "leaf"),
# )

PERMS = (
    ("device.name.all.read", "READ", "device.name.all"),
    ("device.name.all.write", "WRITE", "device.name.all"),
    ("device.status.all.read", "READ", "device.status.all"),
    ("device.status.all.write", "WRITE", "device.status.all"),
    ("device.description.all.read", "READ", "device.description.all"),
    ("device.description.all.write", "WRITE", "device.description.all"),
)

GROUPS = (
    (
        "Network Engineer",
        "network-engineer",
        (
            "device.name.all.read",
            "device.status.all.read",
            "device.description.all.read",
            "device.name.all.write",
            "device.status.all.write",
            "device.description.all.write",
        ),
    ),
    (
        "Operator",
        "operator",
        (
            "device.name.all.read",
            "device.status.all.read",
            "device.description.all.read",
            "device.description.all.write",
        ),
    ),
    ("Manager", "manager", ("device.name.all.read", "device.status.all.read", "device.description.all.read")),
)

ACCOUNTS = (
    ("ozzie", "User", ("operator",)),
    ("nelly", "User", ("network-engineer", "operator")),
    ("mary", "User", ("manager",)),
)

INTERFACE_ROLES = {
    "spine": ["leaf", "leaf", "leaf", "leaf", "leaf", "leaf"],
    "leaf": ["spine", "spine", "spine", "spine", "server", "server"],
}

log = get_logger()


async def load_data(db: InfrahubDatabase, nbr_devices: int = 0) -> None:
    # ------------------------------------------
    # Create User Accounts and Groups
    # ------------------------------------------
    groups_dict = {}
    # tags_dict = {}

    for group in GROUPS:
        obj = await Node.init(db=db, schema=CoreGroup)
        await obj.new(db=db, description=group[0], name=group[1])
        await obj.save(db=db)
        groups_dict[group[1]] = obj
        log.info(f"Group Created: {obj.name.value}")

    # ------------------------------------------
    # Create Status, Role & DeviceProfile
    # ------------------------------------------
    # statuses_dict = {}
    # roles_dict = {}

    log.info("Creating Site")
    site_hq = await Node.init(db=db, schema="LocationSite")
    await site_hq.new(db=db, name="HQ")
    await site_hq.save(db=db)

    active_status = "active"
    role_loopback = "loopback"

    log.info("Creating Device")
    for idx, device in enumerate(DEVICES):
        if nbr_devices and nbr_devices <= idx:
            continue

        status = device[1]

        role = None
        if device[4]:
            role = device[4]
        device_obj = await Node.init(db=db, schema="InfraDevice")
        await device_obj.new(db=db, name=device[0], status=status, type=device[2], role=role, site=site_hq)

        await device_obj.save(db=db)
        log.info(f"- Created Device: {device[0]}")

        # Add a special interface for spine1
        if device[0] == "spine1":
            intf = await Node.init(db=db, schema="InfraInterfaceL3")
            await intf.new(
                db=db,
                device="spine1",
                name="Loopback0",
                enabled=True,
                status=active_status,
                role=role_loopback,
                speed=10000,
            )
            await intf.save(db=db)

            ip = await Node.init(db=db, schema="IpamIPAddress")
            await ip.new(db=db, interface=intf, address=f"192.168.{idx}.10/24")
            await ip.save(db=db)

        if device[4] not in ["spine", "leaf"]:
            continue

        # Create and connect interfaces
        INTERFACES = ["Ethernet0", "Ethernet1", "Ethernet2"]
        for intf_idx, intf_name in enumerate(INTERFACES):
            intf_role = INTERFACE_ROLES[device[4]][intf_idx]
            # intf_role_id = roles_dict[intf_role].id

            enabled = True
            if intf_idx in [0, 1]:
                enabled = False

            intf = await Node.init(db=db, schema="InfraInterfaceL3")
            await intf.new(
                db=db,
                device=device_obj,
                name=intf_name,
                speed=10000,
                enabled=enabled,
                status=active_status,
                role=intf_role,
            )
            await intf.save(db=db)

            if intf_idx == 1:
                ip = await Node.init(db=db, schema="IpamIPAddress")
                await ip.new(db=db, interface=intf, address=f"192.168.{idx}.{intf_idx}/24")
                await ip.save(db=db)
