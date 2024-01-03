import re
from collections import defaultdict

from infrahub.log import get_logger

# flake8: noqa
# pylint: skip-file

ROLES = ["spine", "leaf", "firewall", "server", "uplink"]

DEVICES = (
    ("spine1", "active", "7050X3", "profile1", "spine", ["red", "green"]),
    ("spine2", "active", "QFX5100", "profile1", "spine", ["red", "blue", "green"]),
    ("spine3", "drained", "QFX5100", "profile1", "spine", ["red", "blue"]),
    ("spine4", "active", "7050X3", "profile1", "spine", ["blue", "green"]),
    ("leaf1", "active", "QFX5100", None, "leaf", ["red", "blue"]),
    ("leaf2", "maintenance", "QFX5100", "profile2", "leaf", ["red", "blue", "green"]),
    ("leaf3", "active", "7050X3", None, "leaf", ["blue", "green"]),
)

INTERFACE_NAMES = {
    "QFX5100": ["xe-0/0/0", "xe-0/0/1", "xe-0/0/2", "xe-0/0/3", "xe-0/0/4", "xe-0/0/5"],
    "7050X3": ["Ethernet1", "Ethernet2", "Ethernet3", "Ethernet4", "Ethernet5"],
}

INTERFACE_ROLES = {
    "spine": ["leaf", "leaf", "leaf", "leaf", "leaf", "leaf"],
    "leaf": ["spine", "spine", "spine", "spine", "server", "server"],
}

INTERFACE_OBJS = defaultdict(list)

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
    ("site-builder", "Script", ("operator",)),
    # ("nelly", "User", ("network-engineer", "operator")),
    # ("mary", "User", ("manager",)),
)

log = get_logger()


def load_data():
    # ------------------------------------------
    # Create User Accounts and Groups
    # ------------------------------------------
    groups_dict = {}
    accounts_dict = {}
    tags_dict = {}

    # for perm in PERMS:
    #     obj = Permission.init(name=perm[0], type=perm[1])
    #     obj.save()
    #     perms_dict[perm[0]] = obj

    #     # Associate the permissions with the right attr group
    #     grp = registry.attr_group[perm[2]]
    #     add_relationship(obj, grp, f"CAN_{obj.type.value}")

    #     log.info(f"Permission Created: {obj.name.value}")

    # # Import the existing groups into the dict
    # groups = Group.get_list()
    # for group in groups:
    #     groups_dict[group.slug.value] = group

    for group in GROUPS:
        obj = Group.init(label=group[0], name=group[1])
        obj.save()
        groups_dict[group[1]] = obj
        log.info(f"Group Created: {obj.label.value}")

        # for perm_name in group[2]:
        #     perm = perms_dict[perm_name]

        #     # Associate the permissions with the right attr group
        #     add_relationship(obj, perm, f"HAS_PERM")

    for account in ACCOUNTS:
        obj = Account.init(name=account[0], type=account[1])
        obj.save()
        accounts_dict[account[0]] = obj

        for group in account[2]:
            groups_dict[group].add_account(obj)

        log.info(f"Account Created: {obj.name.value}")

    # ------------------------------------------
    # Create Status, Role & DeviceProfile
    # ------------------------------------------
    statuses_dict = {}
    roles_dict = {}

    log.info("Creating Roles & Status")
    for role in ROLES:
        obj = Role.init(label=role.title(), slug=role)
        obj.save()
        roles_dict[role] = obj
        log.info(f"Created Role: {role}")

    STATUSES = ["active", "provisionning", "maintenance", "drained"]
    for status in STATUSES:
        obj = Status.init(label=status.title(), slug=status)
        obj.save()
        statuses_dict[status] = obj
        log.info(f"Created Status: {status}")

    TAGS = ["blue", "green", "red"]
    for tag in TAGS:
        obj = Tag.init(name=tag)
        obj.save()
        tags_dict[tag] = obj
        log.info(f"Created Tag: {tag}")

    active_status = statuses_dict["active"]
    site_builder_account = accounts_dict["site-builder"]

    log.info("Creating Device")
    for idx, device in enumerate(DEVICES):
        status_id = statuses_dict[device[1]].id
        role_id = roles_dict[device[4]].id
        device_type = device[2]

        obj = Device.init(name=device[0], status=status_id, type=device[2], role=role_id, source=site_builder_account)

        # Connect tags
        for tag_name in device[5]:
            tag = tags_dict[tag_name]
            obj.tags.add_peer(tag)

        obj.save()
        log.info(f"- Created Device: {device[0]}")

        # # Add a special interface for spine1
        # if device[0] == "spine1":
        #     intf = Interface.init(device="spine1", name="Loopback0", enabled=True)
        #     intf.save()

        #     ip = IPAddress.init(interface=intf.uuid, address=f"192.168.{idx}.10/24")
        #     ip.save()

        for intf_idx, intf_name in enumerate(INTERFACE_NAMES[device_type]):
            device_id = str(re.search(r"\d+", device[0]).group())

            intf_role = INTERFACE_ROLES[device[4]][intf_idx]
            intf_role_id = roles_dict[intf_role].id

            intf = Interface.init(
                device=obj.uuid,
                name=intf_name,
                speed=10000,
                enabled=True,
                status=active_status.id,
                role=intf_role_id,
                source=site_builder_account,
            )
            intf.save()

            INTERFACE_OBJS[device[0]].append(intf)

            device_id = str(re.search(r"\d+", device[0]).group())

            if "spine" in device[0]:
                network = f"192.168.{device_id}{intf_idx+1}.1/30"
            elif "leaf" in device[0]:
                network = f"192.168.{intf_idx+1}{device_id}.2/30"

                spine_name = f"spine{intf_idx+1}"
                if spine_name in INTERFACE_OBJS.keys():
                    intf.connected_interface.add_peer(INTERFACE_OBJS[spine_name][int(device_id) - 1])
                    if intf_idx != 0:
                        intf.description.value = f"Connected to {spine_name}"
                    intf.save()

            ip = IPAddress.init(interface=intf.uuid, address=network, source=site_builder_account)
            ip.save()
