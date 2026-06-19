"""Typed handles returned by the data-slice fixtures.

A handle is the slice's public surface: the ids of what it created, keyed the
way downstream slices look them up (mirroring the keys the monolithic script
kept in ``client.store``). Handles replace the script's hidden in-process state
so each slice can be loaded — and reasoned about — independently.

In external mode (``INFRAHUB_ADDRESS`` set, nothing loaded by the suite) every
slice returns ``<Handle>.external()``: an empty handle that downstream slices
must not dereference — they no-op too, so the chain never does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self


@dataclass(frozen=True)
class _BaseHandle:
    loaded: bool = field(default=True, kw_only=True)

    @classmethod
    def external(cls) -> Self:
        """The empty handle returned (and never dereferenced) in external mode."""
        return cls(loaded=False)


@dataclass(frozen=True)
class RbacHandle(_BaseHandle):
    """Accounts, account groups, roles and the demo object permission.

    Keys mirror the script's store keys: accounts by username (``pop-builder``,
    ``crm-sync``, ``cobrian``...), groups by short key (``administrators``,
    ``ops-team``, ``eng-team``, ``arch-team``). ``pop-builder``/``crm-sync``
    account ids and the ``eng-team``/``ops-team`` group ids are used as
    attribute ``source``/``owner`` metadata throughout the other slices.
    """

    accounts: dict[str, str] = field(default_factory=dict)
    groups: dict[str, str] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    permissions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LocationsHandle(_BaseHandle):
    """Continents and countries, by name (sites attach to a country)."""

    continents: dict[str, str] = field(default_factory=dict)
    countries: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OrgRegistryHandle(_BaseHandle):
    """Organizations, platforms, tags, ASNs and BGP peer groups.

    ``asns`` is keyed by organization name (the script stored ASNs that way:
    the internal AS is ``asns["Duff"]`` = AS64496).
    """

    organizations: dict[str, str] = field(default_factory=dict)
    platforms: dict[str, str] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    asns: dict[str, str] = field(default_factory=dict)
    peer_groups: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfilesGroupsHandle(_BaseHandle):
    """Interface profiles (by profile_name) and standard groups (by name)."""

    interface_profiles: dict[str, str] = field(default_factory=dict)
    standard_groups: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IpamPoolsHandle(_BaseHandle):
    """Resource pools by display name, plus the standalone seeded prefixes.

    ``pools`` keys: "Internal networks pool", "Loopbacks pool",
    "Interconnections pool", "Management addresses pool",
    "External prefixes pool", "Internal networks pool (IPv6)".
    ``prefixes`` is keyed by prefix string (e.g. "10.0.0.0/8").
    """

    pools: dict[str, str] = field(default_factory=dict)
    prefixes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PatchTemplateHandle(_BaseHandle):
    """The Regular_Patch_Panel object template and its interface templates."""

    templates: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SitesHandle(_BaseHandle):
    """The five sites and everything generate_site created inside them.

    Replaces the script's in-process state: ``loopback_ips`` mirrors the
    ``<device>-loopback-ip`` store keys (the BGP mesh builds sessions from
    them), ``backbone_interface_ids`` mirrors the module-global
    ``INTERFACE_OBJS`` (per edge device, the ORDERED [Ethernet3, Ethernet4]
    interface ids that create_backbone_connectivity pops from), and ``vlans``
    mirrors the ``<site>_<role>`` store keys.
    """

    sites: dict[str, str] = field(default_factory=dict)
    devices: dict[str, str] = field(default_factory=dict)
    # device name -> the address VALUE (e.g. "10.0.0.1/32"); the mesh needs values, not ids.
    loopback_ips: dict[str, str] = field(default_factory=dict)
    # edge device name -> ordered backbone-role interface ids ([Ethernet3, Ethernet4]).
    backbone_interface_ids: dict[str, list[str]] = field(default_factory=dict)
    # "<site>_<role>" (e.g. "atl1_server") -> VLAN id.
    vlans: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TopologyHandle(_BaseHandle):
    """Marker for the cross-site stage: profiles/groups applied, BGP mesh, backbone.

    Nothing downstream selects topology objects by id; the handle records what
    was built so scenario slices (and the parity dump) can depend on the stage
    having completed.
    """

    backbone_services: tuple[str, ...] = ()
    internal_sessions: int = 0


@dataclass(frozen=True)
class ScenarioBranchesHandle(_BaseHandle):
    """The seeded scenario branches, by branch name."""

    branches: tuple[str, ...] = ()
