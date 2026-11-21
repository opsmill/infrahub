// PROTOTYPE design-jam schema-migrations
// Mock records shaped after the INFP-719 engineering investigation, and stand-ins for the pages around the views; revisions copy from this file and never edit it.
import { Button, Card, Meter, Tooltip } from "@infrahub/ui";
import { formatDistanceToNowStrict } from "date-fns";
import { createContext, type ReactNode, useContext, useState } from "react";

import { Col, Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import Content from "@/shared/components/layout/content";
import { HeaderContainer } from "@/shared/components/layout/header-container";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

/* ------------------------------------------------------------------ scenes */

export const SCENES = [
  "Staged schema change",
  "Schema difference",
  "Branch history",
  "Main history",
  "Apply running",
  "Proposed change review",
  "Merge rolled back",
] as const;
export type Scene = (typeof SCENES)[number];

export const IMPACT_STATES = ["done", "running", "failed", "out of date", "conflict"] as const;
export type ImpactState = (typeof IMPACT_STATES)[number];

/* ------------------------------------------------------------------ records */

export type Section = "attributes" | "relationships";

export type Operation =
  | { op: "node_add"; kind: string }
  | { op: "node_remove"; kind: string }
  | { op: "node_prop"; kind: string; prop: string; before: string; value: string }
  | { op: "el_add"; kind: string; section: Section; name: string; detail: string }
  | { op: "el_remove"; kind: string; section: Section; name: string }
  | {
      op: "el_prop";
      kind: string;
      section: Section;
      name: string;
      prop: string;
      before: string;
      value: string;
    };

export type ChangeStatus = "staged" | "running" | "applied" | "failed";
export type ApplicationStatus = "running" | "applied" | "failed" | "rolled back" | "skipped";
export type MigrationStatus =
  | "waiting"
  | "running"
  | "applied"
  | "failed"
  | "rolled back"
  | "cancelled";

export type Deletion = { count: number; what: "nodes" | "values" | "peers" };

export type Migration = {
  name: string;
  path: string;
  status: MigrationStatus;
  nodes: number;
  completed: number;
  deletes?: Deletion;
  error?: string;
};

export type Application = {
  at: string;
  status: ApplicationStatus;
  error?: string;
  migrations: Migration[];
};

export type SchemaChange = {
  id: string;
  name: string;
  version: number | null;
  status: ChangeStatus;
  parent: string | null;
  createdAt: string;
  appliedAt?: string;
  operations: Operation[];
  applications: Application[];
  fromUpgrade?: boolean;
};

export type Violation = {
  constraint: string;
  path: string;
  nodeId: string;
  nodeKind: string;
  nodeLabel: string | null;
  message: string;
};

export type Impact = {
  status: "running" | "done" | "failed";
  calculatedAt: string;
  outOfDate: boolean;
  error?: string;
  migrations: Migration[];
  violations: Violation[];
  denied: { kind: string; path: string; count: number }[];
  constraints: { name: string; path: string; violations: number }[];
  conflicts: string[];
};

export type ProposedChange = {
  id: string;
  name: string;
  source: string;
  destination: string;
  mainVersion: number;
  replay: SchemaChange[];
};

/* ------------------------------------------------------------------ names */

const NOW = Date.now();
const minutesAgo = (minutes: number) => new Date(NOW - minutes * 60_000).toISOString();

export const MAIN = "main";
export const BRANCH = "feature/dc2-paris-edge-routers-device-role-and-site-shortname";

export const pad = (version: number) => String(version).padStart(5, "0");
export const changeName = (c: SchemaChange) =>
  c.version === null ? c.name : `${pad(c.version)}_${c.name}`;

export const MIGRATION_LABEL: Record<string, string> = {
  "node.attribute.add": "Add attribute",
  "node.attribute.remove": "Remove attribute",
  "node.relationship.remove": "Remove relationship",
  "node.remove": "Remove node kind",
  "node.inherit_from.update": "Change inherited generics",
  "node.name.update": "Rename node kind",
  "node.namespace.update": "Change namespace",
  "node.uniqueness_constraints.update": "Change uniqueness constraints",
  "attribute.name.update": "Rename attribute",
  "attribute.kind.update": "Change attribute kind",
  "attribute.unique.update": "Make attribute unique",
  "attribute.read_only.update": "Change read-only",
  "attribute.optional.update": "Make attribute mandatory",
};

/* ------------------------------------------------------------------ staged */

const LABEL_KINDS = [
  "InfraDevice",
  "InfraInterfaceL3",
  "InfraInterfaceL2",
  "LocationSite",
  "LocationRack",
  "InfraCircuit",
  "InfraProvider",
  "InfraPlatform",
  "InfraVLAN",
  "InfraBGPSession",
  "InfraAutonomousSystem",
  "IpamIPAddress",
  "IpamPrefix",
  "OrganizationTenant",
  "InfraCircuitTerminationEndpointInterfaceAssignment",
];

const STAGED_OPERATIONS: Operation[] = [
  {
    op: "el_add",
    kind: "InfraDevice",
    section: "attributes",
    name: "role",
    detail: "Dropdown, mandatory, default leaf, choices leaf, spine, border",
  },
  { op: "el_remove", kind: "InfraInterface", section: "attributes", name: "mtu_legacy" },
  {
    op: "el_prop",
    kind: "LocationSite",
    section: "attributes",
    name: "shortname",
    prop: "optional",
    before: "true",
    value: "false",
  },
  { op: "el_remove", kind: "InfraCircuit", section: "relationships", name: "provider_contact" },
  {
    op: "el_prop",
    kind: "InfraCircuitTerminationEndpointInterfaceAssignment",
    section: "attributes",
    name: "description",
    prop: "name",
    before: "description",
    value: "termination_notes",
  },
  { op: "node_remove", kind: "InfraLegacyPatchPanel" },
  {
    op: "el_prop",
    kind: "DcimCloudDevice",
    section: "attributes",
    name: "serial",
    prop: "unique",
    before: "false",
    value: "true",
  },
  {
    op: "el_prop",
    kind: "InfraSecretVaultBinding",
    section: "attributes",
    name: "vault_path",
    prop: "optional",
    before: "true",
    value: "false",
  },
  ...LABEL_KINDS.map(
    (kind): Operation => ({
      op: "el_prop",
      kind,
      section: "attributes",
      name: "description",
      prop: "label",
      before: "Description",
      value: "Notes",
    })
  ),
];

const waiting = (name: string, path: string, nodes: number, deletes?: Deletion): Migration => ({
  name,
  path,
  status: "waiting",
  nodes,
  completed: 0,
  deletes,
});

export const STAGED_MIGRATIONS: Migration[] = [
  waiting("node.attribute.add", "InfraDevice.role", 12_480),
  waiting("node.attribute.add", "ProfileInfraDevice.role", 4),
  waiting("node.attribute.remove", "InfraInterfaceL2.mtu_legacy", 31_050, {
    count: 30_112,
    what: "values",
  }),
  waiting("node.attribute.remove", "InfraInterfaceL3.mtu_legacy", 17_163, {
    count: 11_865,
    what: "values",
  }),
  waiting("attribute.optional.update", "LocationSite.shortname", 1302),
  waiting("node.relationship.remove", "InfraCircuit.provider_contact", 316, {
    count: 18,
    what: "peers",
  }),
  waiting(
    "attribute.name.update",
    "InfraCircuitTerminationEndpointInterfaceAssignment.description",
    2204
  ),
  waiting("node.remove", "InfraLegacyPatchPanel", 87, { count: 87, what: "nodes" }),
  waiting("attribute.unique.update", "DcimCloudDevice.serial", 640),
  waiting("node.uniqueness_constraints.update", "DcimCloudDevice", 640),
  waiting("attribute.optional.update", "InfraSecretVaultBinding.vault_path", 1204),
];

const VIOLATIONS: Violation[] = [
  {
    constraint: "attribute.optional.update",
    path: "LocationSite.shortname",
    nodeId: "18a4c2f0-6b1e-4a7d-9c3e-2f5b8d1a7e40",
    nodeKind: "LocationSite",
    nodeLabel: "Paris DC2 – Building B – Hall 3 – Row 14",
    message: "shortname has no value, and the attribute becomes mandatory",
  },
  {
    constraint: "attribute.optional.update",
    path: "LocationSite.shortname",
    nodeId: "18a4c2f0-7d2a-4e19-b0f4-9a3c6e2d1b55",
    nodeKind: "LocationSite",
    nodeLabel: "Frankfurt FR5 – Campus North – Data Hall 12",
    message: "shortname has no value, and the attribute becomes mandatory",
  },
  {
    constraint: "attribute.optional.update",
    path: "LocationSite.shortname",
    nodeId: "1872b7c4-9d1e-4f39-a8b1-6e0c3f5d2a91",
    nodeKind: "LocationSite",
    nodeLabel: null,
    message: "shortname has no value, and the attribute becomes mandatory",
  },
  {
    constraint: "attribute.unique.update",
    path: "DcimCloudDevice.serial",
    nodeId: "18b0e7a2-11c3-4d6f-8e2a-c4f19b7d3a08",
    nodeKind: "DcimCloudDevice",
    nodeLabel: "aws-eu-west-3-edge-router-01",
    message: "serial SN-7HX2-0041 is also used by aws-eu-west-3-edge-router-02",
  },
  {
    constraint: "attribute.unique.update",
    path: "DcimCloudDevice.serial",
    nodeId: "18b0e7a2-22d4-4e7a-9f3b-d5a20c8e4b19",
    nodeKind: "DcimCloudDevice",
    nodeLabel: "aws-eu-west-3-edge-router-02",
    message: "serial SN-7HX2-0041 is also used by aws-eu-west-3-edge-router-01",
  },
  {
    constraint: "node.uniqueness_constraints.update",
    path: "DcimCloudDevice",
    nodeId: "18b0e7a2-11c3-4d6f-8e2a-c4f19b7d3a08",
    nodeKind: "DcimCloudDevice",
    nodeLabel: "aws-eu-west-3-edge-router-01",
    message: "the uniqueness constraint serial is already used by aws-eu-west-3-edge-router-02",
  },
  {
    constraint: "node.uniqueness_constraints.update",
    path: "DcimCloudDevice",
    nodeId: "18b0e7a2-22d4-4e7a-9f3b-d5a20c8e4b19",
    nodeKind: "DcimCloudDevice",
    nodeLabel: "aws-eu-west-3-edge-router-02",
    message: "the uniqueness constraint serial is already used by aws-eu-west-3-edge-router-01",
  },
];

const CONSTRAINTS: Impact["constraints"] = [
  { name: "attribute.optional.update", path: "LocationSite.shortname", violations: 3 },
  { name: "attribute.unique.update", path: "DcimCloudDevice.serial", violations: 2 },
  { name: "node.uniqueness_constraints.update", path: "DcimCloudDevice", violations: 2 },
  { name: "attribute.optional.update", path: "InfraSecretVaultBinding.vault_path", violations: 41 },
  { name: "node.attribute.add", path: "InfraDevice.role", violations: 0 },
  { name: "node.attribute.add", path: "ProfileInfraDevice.role", violations: 0 },
  {
    name: "attribute.name.update",
    path: "InfraCircuitTerminationEndpointInterfaceAssignment.description",
    violations: 0,
  },
  { name: "node.relationship.remove", path: "InfraCircuit.provider_contact", violations: 0 },
  { name: "node.remove", path: "InfraLegacyPatchPanel", violations: 0 },
];

export const STAGED_CHANGE: SchemaChange = {
  id: "staged",
  name: "infradevice_role_add_and_22_more",
  version: null,
  status: "staged",
  parent: "00030_infrabgpsession_add_bfd_profile",
  createdAt: minutesAgo(15),
  operations: STAGED_OPERATIONS,
  applications: [],
};

export function stagedImpact(state: ImpactState): Impact {
  const base: Impact = {
    status: "done",
    calculatedAt: minutesAgo(14),
    outOfDate: false,
    migrations: STAGED_MIGRATIONS,
    violations: VIOLATIONS,
    denied: [
      { kind: "InfraSecretVaultBinding", path: "InfraSecretVaultBinding.vault_path", count: 41 },
    ],
    constraints: CONSTRAINTS,
    conflicts: [],
  };
  if (state === "running")
    return {
      ...base,
      status: "running",
      migrations: [],
      violations: [],
      denied: [],
      constraints: [],
    };
  if (state === "failed")
    return {
      ...base,
      status: "failed",
      error:
        "The check attribute.unique.update on DcimCloudDevice.serial raised an error: the query timed out after 300 seconds.",
      migrations: [],
      violations: [],
      denied: [],
      constraints: [],
    };
  if (state === "out of date") return { ...base, outOfDate: true };
  if (state === "conflict")
    return {
      ...base,
      outOfDate: true,
      conflicts: [
        "InfraCircuit.provider_contact: the staged schema removes this relationship, but the branch no longer has it.",
        "LocationSite.shortname: optional was changed on the branch after staging, from true to false.",
      ],
    };
  return base;
}

/* ------------------------------------------------------------------ history */

const applied = (
  at: string,
  migrations: Migration[],
  status: ApplicationStatus = "applied"
): Application => ({
  at,
  status,
  migrations: migrations.map((m) => ({
    ...m,
    status: status === "applied" ? "applied" : m.status,
    completed: status === "applied" ? m.nodes : m.completed,
  })),
});

const M = (name: string, path: string, nodes: number, deletes?: Deletion) =>
  waiting(name, path, nodes, deletes);

const REBASE = "2026-11-12T08:15:00Z";

export const BRANCH_HISTORY: SchemaChange[] = [
  {
    id: "b25",
    name: "dcimgenericdevice_serial_add",
    version: 25,
    status: "applied",
    parent: "00024_ipamprefix_add_utilization_threshold",
    createdAt: "2026-10-29T09:02:00Z",
    appliedAt: "2026-10-29T09:03:00Z",
    operations: [
      {
        op: "el_add",
        kind: "DcimGenericDevice",
        section: "attributes",
        name: "serial",
        detail: "Text, optional",
      },
    ],
    applications: [
      applied("2026-10-29T09:03:00Z", [
        M("node.attribute.add", "DcimCloudDevice.serial", 640),
        M("node.attribute.add", "DcimPhysicalDevice.serial", 9830),
      ]),
      applied(REBASE, [
        M("node.attribute.add", "DcimCloudDevice.serial", 640),
        M("node.attribute.add", "DcimPhysicalDevice.serial", 9830),
      ]),
    ],
  },
  {
    id: "b26",
    name: "locationsite_add_region",
    version: 26,
    status: "applied",
    parent: "00025_dcimgenericdevice_serial_add",
    createdAt: "2026-10-30T14:20:00Z",
    appliedAt: "2026-10-30T14:21:00Z",
    operations: [
      {
        op: "el_add",
        kind: "LocationSite",
        section: "attributes",
        name: "region",
        detail: "Dropdown, optional, choices emea, amer, apac",
      },
    ],
    applications: [
      applied("2026-10-30T14:21:00Z", [M("node.attribute.add", "LocationSite.region", 1302)]),
      applied(REBASE, [M("node.attribute.add", "LocationSite.region", 1302)]),
    ],
  },
  {
    id: "b27",
    name: "infraplatform_description_label",
    version: 27,
    status: "applied",
    parent: "00026_locationsite_add_region",
    createdAt: "2026-11-02T11:00:00Z",
    appliedAt: "2026-11-02T11:00:00Z",
    operations: [
      {
        op: "el_prop",
        kind: "InfraPlatform",
        section: "attributes",
        name: "description",
        prop: "label",
        before: "Description",
        value: "Platform notes",
      },
    ],
    applications: [applied("2026-11-02T11:00:00Z", []), applied(REBASE, [])],
  },
  {
    id: "b28",
    name: "infracircuit_add_commit_rate_and_3_more",
    version: 28,
    status: "applied",
    parent: "00027_infraplatform_description_label",
    createdAt: "2026-11-04T16:45:00Z",
    appliedAt: "2026-11-04T16:52:00Z",
    operations: [
      {
        op: "el_add",
        kind: "InfraCircuit",
        section: "attributes",
        name: "commit_rate",
        detail: "Number, optional",
      },
      {
        op: "el_add",
        kind: "InfraCircuit",
        section: "attributes",
        name: "burst_rate",
        detail: "Number, optional",
      },
      {
        op: "el_prop",
        kind: "InfraCircuit",
        section: "attributes",
        name: "circuit_id",
        prop: "unique",
        before: "false",
        value: "true",
      },
      { op: "el_remove", kind: "InfraCircuit", section: "attributes", name: "legacy_billing_code" },
    ],
    applications: [
      applied("2026-11-04T16:52:00Z", [
        M("node.attribute.add", "InfraCircuit.commit_rate", 4918),
        M("node.attribute.add", "InfraCircuit.burst_rate", 4918),
        M("attribute.unique.update", "InfraCircuit.circuit_id", 4918),
        M("node.attribute.remove", "InfraCircuit.legacy_billing_code", 4918, {
          count: 3377,
          what: "values",
        }),
      ]),
      applied(REBASE, [
        M("node.attribute.add", "InfraCircuit.commit_rate", 4918),
        M("node.attribute.add", "InfraCircuit.burst_rate", 4918),
        M("attribute.unique.update", "InfraCircuit.circuit_id", 4918),
        M("node.attribute.remove", "InfraCircuit.legacy_billing_code", 4918, {
          count: 3377,
          what: "values",
        }),
      ]),
    ],
  },
  {
    id: "b-failed",
    name: "infradevice_asset_tag_kind_update",
    version: null,
    status: "failed",
    parent: null,
    createdAt: "2026-11-06T10:05:00Z",
    operations: [
      {
        op: "el_prop",
        kind: "InfraDevice",
        section: "attributes",
        name: "asset_tag",
        prop: "kind",
        before: "Text",
        value: "Number",
      },
    ],
    applications: [
      {
        at: "2026-11-06T10:05:00Z",
        status: "failed",
        error:
          'attribute.kind.update on InfraDevice.asset_tag failed: 3 nodes hold values that are not numbers ("N/A", "TBD", "pending-audit-2026").',
        migrations: [
          {
            name: "attribute.kind.update",
            path: "InfraDevice.asset_tag",
            status: "failed",
            nodes: 12_480,
            completed: 7200,
            error: '3 nodes hold values that are not numbers ("N/A", "TBD", "pending-audit-2026").',
          },
        ],
      },
    ],
  },
  {
    id: "b29",
    name: "locationrack_height_optional_update",
    version: 29,
    status: "applied",
    parent: "00028_infracircuit_add_commit_rate_and_3_more",
    createdAt: "2026-11-13T09:30:00Z",
    appliedAt: "2026-11-13T09:31:00Z",
    operations: [
      {
        op: "el_prop",
        kind: "LocationRack",
        section: "attributes",
        name: "height",
        prop: "optional",
        before: "true",
        value: "false",
      },
    ],
    applications: [
      applied("2026-11-13T09:31:00Z", [
        M("attribute.optional.update", "LocationRack.height", 6412),
      ]),
    ],
  },
  {
    id: "b30",
    name: "infrabgpsession_add_bfd_profile",
    version: 30,
    status: "applied",
    parent: "00029_locationrack_height_optional_update",
    createdAt: "2026-11-14T15:10:00Z",
    appliedAt: "2026-11-14T15:12:00Z",
    operations: [
      {
        op: "el_add",
        kind: "InfraBGPSession",
        section: "relationships",
        name: "bfd_profile",
        detail: "peer InfraBFDProfile, cardinality one, optional",
      },
    ],
    applications: [applied("2026-11-14T15:12:00Z", [])],
  },
];

const MAIN_SUMMARIES = [
  "infraplatform_add_vendor",
  "locationsite_add_timezone",
  "infradevice_add_serial_number",
  "ipamprefix_add_role",
  "infrainterface_add_lag_and_2_more",
  "organizationtenant_add_contract_id",
  "infravlan_name_update",
  "infracircuit_add_provider_contact",
  "locationrack_add_height",
  "infraprovider_add_support_portal",
  "infrabgpsession_add_import_policies_and_5_more",
  "ipamipaddress_add_dns_name",
  "infraautonomoussystem_description_label",
  "locationbuilding_remove",
  "infradevice_platform_optional_update",
  "infralegacypatchpanel_add",
  "infrainterfacel3_add_vrf",
  "dcimgenericdevice_add_asset_tag",
  "infracircuitterminationendpointinterfaceassignment_add",
  "infraplatform_add_napalm_driver",
  "ipamnamespace_add_default",
  "infravlan_add_vlan_group",
  "locationsite_add_facility_code",
  "ipamprefix_add_utilization_threshold",
  "infradevice_add_maintenance_window",
  "locationrack_add_power_feed_and_1_more",
  "infraprovider_add_account_manager",
];

export const MAIN_HISTORY: SchemaChange[] = [
  {
    id: "m0",
    name: "upgrade_and_56_more",
    version: 0,
    status: "applied",
    parent: null,
    createdAt: "2026-09-30T07:00:00Z",
    appliedAt: "2026-09-30T07:00:00Z",
    fromUpgrade: true,
    operations: LABEL_KINDS.slice(0, 12).map((kind) => ({ op: "node_add", kind })),
    applications: [applied("2026-09-30T07:00:00Z", [])],
  },
  {
    id: "m-failed-1",
    name: "ipamprefix_member_type_kind_update",
    version: null,
    status: "failed",
    parent: null,
    createdAt: "2026-10-02T13:44:00Z",
    operations: [
      {
        op: "el_prop",
        kind: "IpamPrefix",
        section: "attributes",
        name: "member_type",
        prop: "kind",
        before: "Dropdown",
        value: "Text",
      },
    ],
    applications: [
      {
        at: "2026-10-02T13:44:00Z",
        status: "failed",
        error:
          "attribute.kind.update on IpamPrefix.member_type failed: the worker stopped during the migration.",
        migrations: [],
      },
    ],
  },
  ...MAIN_SUMMARIES.map(
    (name, i): SchemaChange => ({
      id: `m${i + 1}`,
      name,
      version: i + 1,
      status: "applied",
      parent: i === 0 ? "00000_upgrade_and_56_more" : `${pad(i)}_${MAIN_SUMMARIES[i - 1]}`,
      createdAt: new Date(Date.UTC(2026, 9, 1 + i, 9)).toISOString(),
      appliedAt: new Date(Date.UTC(2026, 9, 1 + i, 9, 2)).toISOString(),
      operations: [
        { op: "node_prop", kind: "InfraDevice", prop: "label", before: "Device", value: "Device" },
      ],
      applications: [applied(new Date(Date.UTC(2026, 9, 1 + i, 9, 2)).toISOString(), [])],
    })
  ),
  {
    id: "m-failed-2",
    name: "organizationtenant_remove",
    version: null,
    status: "failed",
    parent: null,
    createdAt: "2026-10-20T08:12:00Z",
    operations: [{ op: "node_remove", kind: "OrganizationTenant" }],
    applications: [
      {
        at: "2026-10-20T08:12:00Z",
        status: "failed",
        error:
          "node.remove on OrganizationTenant refused: 214 nodes of other kinds have a mandatory relationship to it.",
        migrations: [],
      },
    ],
  },
];

/* ------------------------------------------------------------------ worst case */

// PROTOTYPE design-jam schema-migrations: the break-ui toggle swaps the demo records for the worst
// realistic ones, read once when the page loads.
export const WORST_CASE = new URLSearchParams(window.location.search).get("dj.data") === "worst";

/** The longest values the schema accepts: a kind name past the 32-character name limit already exists. */
const LONG_KIND = "InfraCircuitTerminationEndpointInterfaceAssignment";
const LONG_FIELD = "maintenance_window_contact_email";
const MANY_FAILING = 28_904;

if (WORST_CASE) {
  STAGED_CHANGE.name =
    "infracircuitterminationendpointinterfaceassignment_maintenance_window_contact_email_add_and_24_more";
  STAGED_OPERATIONS.push(
    {
      op: "el_add",
      kind: LONG_KIND,
      section: "attributes",
      name: LONG_FIELD,
      detail:
        "Email, optional, regex ^[a-z0-9._%+-]+@northwind-industries-holdings\\.example\\.com$",
    },
    {
      op: "el_prop",
      kind: "InfraInterfaceL2",
      section: "attributes",
      name: "description",
      prop: "optional",
      before: "true",
      value: "false",
    }
  );
  STAGED_MIGRATIONS.push(
    waiting("node.attribute.add", `${LONG_KIND}.${LONG_FIELD}`, 2204),
    waiting("attribute.optional.update", "InfraInterfaceL2.description", 31_050)
  );
  CONSTRAINTS.push({
    name: "attribute.optional.update",
    path: "InfraInterfaceL2.description",
    violations: MANY_FAILING,
  });
  const first = VIOLATIONS[0];
  if (first)
    first.nodeLabel =
      "Paris DC2 – Building B – Hall 3 – Row 14 – Rack R14-07 – Patch panel PP-03, legacy, remove after the fibre migration";
  for (let i = 0; i < MANY_FAILING; i++)
    VIOLATIONS.push({
      constraint: "attribute.optional.update",
      path: "InfraInterfaceL2.description",
      nodeId: `2c0f${String(i).padStart(4, "0")}-5e1a-4b7d-9c3e-2f5b8d1a7e40`,
      nodeKind: "InfraInterfaceL2",
      nodeLabel: `dc2-par-leaf-${String(Math.floor(i / 48) + 1).padStart(3, "0")} › Ethernet1/${(i % 48) + 1}`,
      message: "description has no value, and the attribute becomes mandatory",
    });
  for (const change of BRANCH_HISTORY) {
    // Every count at exactly 1, where a plural would show.
    if (change.id === "b29")
      change.applications = [
        applied("2026-11-13T09:31:00Z", [M("attribute.optional.update", "LocationRack.height", 1)]),
      ];
    if (change.id === "b28")
      for (const app of change.applications)
        for (const m of app.migrations) if (m.deletes) m.deletes = { count: 1, what: "values" };
    if (change.id === "b-failed")
      for (const app of change.applications)
        app.error = `attribute.kind.update on ${LONG_KIND}.${LONG_FIELD} failed: 3 nodes hold values that are not email addresses ("bartholomew.fitzgerald@northwind-industries-holdings", "n/a", "TBD").`;
  }
}

export const BRANCHED_FROM_VERSION = 24;
export const MAIN_VERSION = 27;

export const revisionOf = (history: SchemaChange[]) =>
  history
    .filter((c) => c.status === "applied" && c.version !== null)
    .reduce<SchemaChange | undefined>(
      (last, c) => (!last || (c.version ?? 0) > (last.version ?? 0) ? c : last),
      undefined
    );

/* ------------------------------------------------------------------ running */

export const RUNNING_APPLICATION: Application = {
  at: minutesAgo(4),
  status: "running",
  migrations: STAGED_MIGRATIONS.map((m, i): Migration => {
    if (i < 2) return { ...m, status: "applied", completed: m.nodes };
    if (i === 2) return { ...m, status: "running", completed: 18_240 };
    if (i === 3) return { ...m, status: "running", completed: 9610 };
    return m;
  }),
};

/* ------------------------------------------------------------------ proposed change */

export const PROPOSED_CHANGE: ProposedChange = {
  id: "142",
  name: "Add device role and site short name to the Paris DC2 edge routers, and remove the legacy MTU attribute",
  source: BRANCH,
  destination: MAIN,
  mainVersion: MAIN_VERSION,
  replay: BRANCH_HISTORY.filter((c) => c.status === "applied"),
};

export const PC_CHECK = {
  status: "would fail" as const,
  checkedAt: minutesAgo(26),
  failingChangeId: "b29",
  message:
    "2 LocationRack nodes created on main after this branch was created have no value for height, which becomes mandatory.",
  violations: [
    {
      constraint: "attribute.optional.update",
      path: "LocationRack.height",
      nodeId: "18c11a3e-4f0b-4b9e-a2d7-5e81c0f9d322",
      nodeKind: "LocationRack",
      nodeLabel: "Paris DC2 – Hall 3 – Rack R14-07",
      message: "height has no value, and the attribute becomes mandatory",
    },
    {
      constraint: "attribute.optional.update",
      path: "LocationRack.height",
      nodeId: "18c11a3e-5a1c-4c0f-b3e8-6f92d1a0e433",
      nodeKind: "LocationRack",
      nodeLabel: null,
      message: "height has no value, and the attribute becomes mandatory",
    },
  ] satisfies Violation[],
};

export const MERGE_ATTEMPT = {
  at: minutesAgo(104),
  failedChangeId: "b29",
  error:
    "attribute.optional.update on LocationRack.height failed: 2 LocationRack nodes created on main have no value for height.",
  applications: PROPOSED_CHANGE.replay.map(
    (c): { change: SchemaChange; status: ApplicationStatus | "not run" } => {
      if (c.id === "b29") return { change: c, status: "failed" };
      if ((c.version ?? 0) > 29) return { change: c, status: "not run" };
      return { change: c, status: "rolled back" };
    }
  ),
};

/* ------------------------------------------------------------------ formatting */

const NUMBER = new Intl.NumberFormat("en-US");
export const fmt = (n: number) => NUMBER.format(n);

export const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);

export function deletionTotals(migrations: Migration[]) {
  const totals = { nodes: 0, values: 0, peers: 0 };
  for (const m of migrations) if (m.deletes) totals[m.deletes.what] += m.deletes.count;
  return totals;
}

export function Num({ value, className }: { value: number; className?: string }) {
  return <span className={classNames("tabular-nums", className)}>{fmt(value)}</span>;
}

/** Names of schema changes, kinds and fields: a monospace font up to one-list rev 3, the app's font after. */
export const IdentifierFont = createContext<"mono" | "app">("mono");

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  const font = useContext(IdentifierFont);
  return (
    <span
      className={classNames(
        font === "mono" ? "break-all font-mono text-xs" : "wrap-anywhere",
        className
      )}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ status */

type BadgeVariant = BadgeProps["variant"];
type StatusLevel = "change" | "application" | "migration";

const STATUS_STYLE: Record<string, { label: string; variant: BadgeVariant; icon: string }> = {
  staged: { label: "Staged", variant: "blue", icon: "mdi:tray-arrow-down" },
  running: { label: "Running", variant: "yellow", icon: "mdi:progress-clock" },
  applied: { label: "Applied", variant: "green", icon: "mdi:check" },
  failed: { label: "Failed", variant: "red", icon: "mdi:close-circle-outline" },
  "rolled back": { label: "Rolled back", variant: "warning", icon: "mdi:undo-variant" },
  skipped: { label: "Skipped", variant: "gray", icon: "mdi:debug-step-over" },
  waiting: { label: "Waiting", variant: "gray-outline", icon: "mdi:clock-outline" },
  "not run": { label: "Not run", variant: "gray-outline", icon: "mdi:minus-circle-outline" },
  cancelled: { label: "Cancelled", variant: "gray-outline", icon: "mdi:cancel" },
};

const UNKNOWN_STATUS = {
  label: "Unknown",
  variant: "gray-outline" as BadgeVariant,
  icon: "mdi:help-circle-outline",
};

export function StatusBadge({ status }: { status: string; level?: StatusLevel }) {
  const style = STATUS_STYLE[status] ?? UNKNOWN_STATUS;
  return (
    <Badge variant={style.variant} className="shrink-0 gap-1">
      <Icon icon={style.icon} aria-hidden="true" />
      {style.label}
    </Badge>
  );
}

/* ------------------------------------------------------------------ operations */

const sectionWord = (s: Section) => (s === "attributes" ? "attribute" : "relationship");

export function OperationText({ op }: { op: Operation }) {
  const kind = <span className="font-medium">{op.kind}</span>;
  switch (op.op) {
    case "node_add":
      return <span>Add node kind {kind}</span>;
    case "node_remove":
      return <span>Remove node kind {kind} and every node of it</span>;
    case "node_prop":
      return (
        <span>
          {kind}: change {op.prop} from <Mono>{op.before}</Mono> to <Mono>{op.value}</Mono>
        </span>
      );
    case "el_add":
      return (
        <span>
          {kind}: add {sectionWord(op.section)} <Mono>{op.name}</Mono>{" "}
          <span className="text-foreground-muted">({op.detail})</span>
        </span>
      );
    case "el_remove":
      return (
        <span>
          {kind}: remove {sectionWord(op.section)} <Mono>{op.name}</Mono>
        </span>
      );
    case "el_prop":
      if (op.prop === "name")
        return (
          <span>
            {kind}: rename {sectionWord(op.section)} <Mono>{op.before}</Mono> to{" "}
            <Mono>{op.value}</Mono>
          </span>
        );
      return (
        <span>
          {kind}.<Mono>{op.name}</Mono>: change {op.prop} from <Mono>{op.before}</Mono> to{" "}
          <Mono>{op.value}</Mono>
        </span>
      );
  }
}

export function OperationList({ operations, limit }: { operations: Operation[]; limit?: number }) {
  const [all, setAll] = useState(false);
  const shown = all || !limit ? operations : operations.slice(0, limit);
  return (
    <Col className="gap-1">
      <ul className="flex flex-col gap-1 text-sm">
        {shown.map((op, i) => (
          <li key={i} className="flex gap-2">
            <Icon
              icon={OP_ICON[op.op]}
              className="mt-0.5 shrink-0 text-foreground-muted"
              aria-hidden="true"
            />
            <OperationText op={op} />
          </li>
        ))}
      </ul>
      {limit && operations.length > limit && (
        <button
          type="button"
          className="self-start text-custom-blue-700 text-sm hover:underline dark:text-custom-blue-300"
          onClick={() => setAll(!all)}
        >
          {all ? "Show fewer operations" : `Show all ${operations.length} operations`}
        </button>
      )}
    </Col>
  );
}

const OP_ICON: Record<Operation["op"], string> = {
  node_add: "mdi:plus-box-outline",
  node_remove: "mdi:minus-box-outline",
  node_prop: "mdi:pencil-box-outline",
  el_add: "mdi:plus",
  el_remove: "mdi:minus",
  el_prop: "mdi:pencil-outline",
};

/* ------------------------------------------------------------------ migrations */

export function MigrationTable({
  migrations,
  mode,
  caption,
}: {
  migrations: Migration[];
  mode: "impact" | "run";
  caption?: string;
}) {
  if (migrations.length === 0) {
    return (
      <p className="px-3 py-2 text-foreground-muted text-sm">
        No migration: this schema change does not change any node.
      </p>
    );
  }
  return (
    <table className="w-full text-sm">
      {caption && <caption className="sr-only">{caption}</caption>}
      <thead className="text-left text-foreground-muted text-xs">
        <tr className="border-b">
          <th className="px-3 py-1.5 font-medium">Migration</th>
          <th className="px-3 py-1.5 font-medium">Kind and field</th>
          <th className="px-3 py-1.5 text-right font-medium">Nodes</th>
          {mode === "impact" ? (
            <th className="px-3 py-1.5 text-right font-medium">Deletes</th>
          ) : (
            <th className="px-3 py-1.5 font-medium">Status</th>
          )}
        </tr>
      </thead>
      <tbody>
        {migrations.map((m) => (
          <tr key={`${m.name}:${m.path}`} className="border-b align-top last:border-b-0">
            <td className="px-3 py-1.5">
              <Tooltip message={<Mono>{m.name}</Mono>}>
                <span>{MIGRATION_LABEL[m.name] ?? m.name}</span>
              </Tooltip>
            </td>
            <td className="px-3 py-1.5">
              <Mono>{m.path}</Mono>
              {m.error && <div className="mt-0.5 text-danger text-xs">{m.error}</div>}
            </td>
            <td className="px-3 py-1.5 text-right">
              {mode === "run" && m.status === "running" ? (
                <Col className="items-end gap-1">
                  <span className="tabular-nums">
                    {fmt(m.completed)} of {fmt(m.nodes)}
                  </span>
                  <Meter
                    aria-label={`${m.path} progress`}
                    value={m.completed}
                    maxValue={m.nodes}
                    className="w-28"
                  />
                </Col>
              ) : (
                <Num value={m.nodes} />
              )}
            </td>
            {mode === "impact" ? (
              <td className="px-3 py-1.5 text-right">
                {m.deletes ? (
                  <span className="text-danger tabular-nums">
                    {fmt(m.deletes.count)} {m.deletes.what}
                  </span>
                ) : (
                  <span className="text-foreground-muted">—</span>
                )}
              </td>
            ) : (
              <td className="px-3 py-1.5">
                <StatusBadge status={m.status} level="migration" />
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ------------------------------------------------------------------ violations */

/** How many more nodes each press of the button lists. */
const MORE_NODES = 100;

function ViolationGroup({
  groupKey,
  items,
  titleWeight,
  nodeLimit,
}: {
  groupKey: string;
  items: Violation[];
  titleWeight: string;
  nodeLimit?: number;
}) {
  const [listed, setListed] = useState(nodeLimit ?? items.length);
  const { constraint, path } = items[0] ?? { constraint: groupKey, path: "" };
  const rest = items.length - listed;
  return (
    <section aria-label={`${constraint} on ${path}`}>
      <h4 className={classNames("flex flex-wrap items-center gap-2 px-3 text-sm", titleWeight)}>
        {MIGRATION_LABEL[constraint] ?? constraint}
        <Mono className="font-normal">{path}</Mono>
        <Badge variant="red">{fmt(items.length)}</Badge>
      </h4>
      <ul className="mt-1 divide-y border-y text-sm">
        {items.slice(0, listed).map((v) => (
          <li
            key={`${v.constraint}${v.nodeId}`}
            className="flex flex-wrap gap-x-3 gap-y-0.5 px-3 py-1.5"
          >
            <a
              href="#node"
              className="font-medium text-custom-blue-700 hover:underline dark:text-custom-blue-300"
            >
              {v.nodeLabel ?? <span className="break-all font-mono text-xs">{v.nodeId}</span>}
            </a>
            <span className="text-foreground-muted">{v.nodeKind}</span>
            <span className="basis-full text-foreground-muted">{v.message}</span>
          </li>
        ))}
        {rest > 0 && (
          <li className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 text-foreground-muted">
            {fmt(listed)} of {fmt(items.length)} nodes listed
            <Button size="xs" variant="outline" onPress={() => setListed((n) => n + MORE_NODES)}>
              List {fmt(Math.min(MORE_NODES, rest))} more
            </Button>
          </li>
        )}
      </ul>
    </section>
  );
}

export function ViolationList({
  violations,
  denied = [],
  limit,
  titleWeight = "font-medium",
  nodeLimit,
}: {
  violations: Violation[];
  denied?: Impact["denied"];
  /** Shows only this many fields; every field when it is not set. */
  limit?: number;
  /** The weight of each field's title. */
  titleWeight?: "font-medium" | "font-semibold";
  /** Lists this many nodes per field first, with a button for more; every node when it is not set. */
  nodeLimit?: number;
}) {
  const groups = new Map<string, Violation[]>();
  for (const v of violations) {
    const key = `${v.constraint}|${v.path}`;
    const group = groups.get(key);
    if (group) group.push(v);
    else groups.set(key, [v]);
  }
  const shown = [...groups.entries()].slice(0, limit);
  const shownDenied = denied.slice(
    0,
    limit === undefined ? undefined : Math.max(0, limit - shown.length)
  );
  return (
    <Col className="gap-3">
      {shown.map(([key, items]) => (
        <ViolationGroup
          key={key}
          groupKey={key}
          items={items}
          titleWeight={titleWeight}
          nodeLimit={nodeLimit}
        />
      ))}
      {shownDenied.map((d) => (
        <section key={d.path} aria-label={`Hidden violations on ${d.path}`}>
          <h4 className={classNames("flex flex-wrap items-center gap-2 px-3 text-sm", titleWeight)}>
            {d.kind}
            <Mono className="font-normal">{d.path}</Mono>
            <Badge variant="red">{fmt(d.count)}</Badge>
          </h4>
          <p className="mt-1 flex gap-2 border-y px-3 py-1.5 text-foreground-muted text-sm">
            <Icon icon="mdi:lock-outline" className="mt-0.5 shrink-0" aria-hidden="true" />
            You do not have permission to view {d.kind} nodes, so only the number of nodes that
            would fail is shown.
          </p>
        </section>
      ))}
    </Col>
  );
}

/* ------------------------------------------------------------------ messages */

const TONE = {
  info: {
    box: "border-border-strong bg-content",
    icon: "mdi:information-outline",
    iconClass: "text-custom-blue-700 dark:text-custom-blue-300",
  },
  warning: {
    box: "border-warning-border bg-warning-surface/60",
    icon: "mdi:alert-outline",
    iconClass: "text-warning",
  },
  danger: {
    box: "border-danger bg-danger-surface",
    icon: "mdi:alert-circle-outline",
    iconClass: "text-danger",
  },
  success: {
    box: "border-border-strong bg-content",
    icon: "mdi:check-circle-outline",
    iconClass: "text-green-700 dark:text-green-400",
  },
} as const;

export function InlineMessage({
  tone,
  title,
  children,
  action,
  className,
}: {
  tone: keyof typeof TONE;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const t = TONE[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={classNames(
        "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm",
        t.box,
        className
      )}
    >
      <Icon
        icon={t.icon}
        className={classNames("mt-0.5 shrink-0 text-base", t.iconClass)}
        aria-hidden="true"
      />
      <div className="min-w-0 grow">
        <div className="font-medium">{title}</div>
        {children && <div className="text-foreground-muted">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ dates */

export function When({ date }: { date: string }) {
  const d = new Date(date);
  return (
    <time dateTime={date} title={d.toLocaleString()}>
      {formatDistanceToNowStrict(d, { addSuffix: true })}
    </time>
  );
}

/* ------------------------------------------------------------------ page stand-ins */

export type TabSpec = { id: string; label: ReactNode; count?: number; live?: boolean };

export function FakeTabs({
  tabs,
  active,
  onSelect,
  label = "Tabs",
}: {
  tabs: TabSpec[];
  active: string;
  onSelect?: (id: string) => void;
  label?: string;
}) {
  return (
    <nav aria-label={label}>
      <Row className="items-end gap-4 overflow-x-auto px-4">
        {tabs.map((t) => {
          const isActive = t.id === active;
          const className = classNames(
            "inline-flex h-11 shrink-0 items-center gap-2 border-b-2 px-3 py-2 font-medium text-sm",
            isActive
              ? "border-custom-blue-600 text-custom-blue-600"
              : "border-transparent text-foreground-muted",
            t.live && !isActive && "hover:border-border-strong hover:text-foreground",
            "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo"
          );
          const content = (
            <>
              {t.label}
              {t.count !== undefined && <Badge className="text-xs">{fmt(t.count)}</Badge>}
            </>
          );
          return t.live && onSelect ? (
            <button
              key={t.id}
              type="button"
              aria-current={isActive ? "page" : undefined}
              className={className}
              onClick={() => onSelect(t.id)}
            >
              {content}
            </button>
          ) : (
            <span key={t.id} aria-current={isActive ? "page" : undefined} className={className}>
              {content}
            </span>
          );
        })}
      </Row>
    </nav>
  );
}

export function ToggleGroup({
  items,
  active,
  onSelect,
  label,
}: {
  items: { id: string; label: ReactNode; icon: string; live?: boolean }[];
  active: string;
  onSelect: (id: string) => void;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="flex gap-1 rounded-md border bg-background p-1 shadow-xs"
    >
      {items.map((it) => {
        const isActive = it.id === active;
        return (
          <button
            key={it.id}
            type="button"
            aria-pressed={isActive}
            disabled={!it.live && !isActive}
            className={classNames(
              "flex items-center gap-1.5 rounded-sm px-3 py-1.5 font-medium text-sm outline-hidden transition-colors",
              "focus-visible:ring-2 focus-visible:ring-ring-halo",
              isActive
                ? "bg-selected text-foreground shadow-xs"
                : "text-foreground-muted enabled:hover:text-foreground"
            )}
            onClick={() => onSelect(it.id)}
          >
            <Icon icon={it.icon} aria-hidden="true" />
            {it.label}
          </button>
        );
      })}
    </div>
  );
}

export const BRANCH_TABS: TabSpec[] = [
  { id: "details", label: "Details" },
  { id: "data", label: "Data" },
  { id: "files", label: "Files" },
  { id: "artifacts", label: "Artifacts" },
  { id: "schema", label: "Schema" },
];

export function BranchPage({
  branch,
  isDefault,
  baseTabs = BRANCH_TABS,
  extraTabs = [],
  active,
  onSelectTab,
  notice,
  headerEnd,
  children,
}: {
  branch: string;
  isDefault?: boolean;
  baseTabs?: TabSpec[] | null;
  extraTabs?: TabSpec[];
  active: string;
  onSelectTab?: (id: string) => void;
  notice?: ReactNode;
  headerEnd?: ReactNode;
  children: ReactNode;
}) {
  const tabs = [...(baseTabs ?? []), ...extraTabs];
  return (
    <Content.Card className="h-full">
      {notice}
      <header>
        <HeaderContainer>
          <h1 className="truncate font-bold text-xl" title={branch}>
            {branch}
          </h1>
          {isDefault && <Badge variant="blue">default</Badge>}
          {headerEnd && <div className="ml-auto shrink-0">{headerEnd}</div>}
        </HeaderContainer>
      </header>
      <Col className="min-h-0 grow gap-0 p-1">
        {tabs.length > 0 && <FakeTabs tabs={tabs} active={active} onSelect={onSelectTab} />}
        <Card variant="panel" className="overflow-auto">
          {children}
        </Card>
      </Col>
    </Content.Card>
  );
}

const PC_TABS: TabSpec[] = [
  { id: "overview", label: "Overview" },
  { id: "data", label: "Data", count: 1214 },
  { id: "files", label: "Files" },
  { id: "artifacts", label: "Artifacts", count: 36 },
  { id: "schema", label: "Schema" },
  { id: "checks", label: "Checks" },
  { id: "tasks", label: "Tasks" },
];

export function ProposedChangePage({
  active,
  schemaCount,
  notice,
  children,
}: {
  active: string;
  schemaCount?: number;
  notice?: ReactNode;
  children: ReactNode;
}) {
  const tabs = PC_TABS.map((t) => (t.id === "schema" ? { ...t, count: schemaCount } : t));
  return (
    <Content.Card className="h-full">
      {notice}
      <header className="flex flex-col gap-1 border-b px-4 py-3">
        <h1 className="font-bold text-xl">{PROPOSED_CHANGE.name}</h1>
        <Row className="flex-wrap items-center gap-2 text-sm">
          <Badge variant="green">Open</Badge>
          <Badge variant="blue" className="max-w-full truncate">
            <Icon icon="mdi:layers-triple" className="mr-1" aria-hidden="true" />
            {PROPOSED_CHANGE.source}
          </Badge>
          <Icon icon="mdi:arrow-right" aria-label="into" />
          <Badge variant="green">
            <Icon icon="mdi:layers-triple" className="mr-1" aria-hidden="true" />
            {PROPOSED_CHANGE.destination}
          </Badge>
          <span className="text-foreground-muted">#{PROPOSED_CHANGE.id}</span>
        </Row>
      </header>
      <FakeTabs tabs={tabs} active={active} />
      <div className="min-h-0 grow overflow-auto">{children}</div>
    </Content.Card>
  );
}

export const SCHEMA_KIND_COUNT = 214;

export function SchemaPage({
  toggles,
  active,
  onSelect,
  children,
}: {
  toggles: { id: string; label: ReactNode; icon: string; live?: boolean }[];
  active: string;
  onSelect: (id: string) => void;
  children: ReactNode;
}) {
  return (
    <Content.Card className="h-full">
      <Content.CardTitle
        title="Schema"
        badgeContent={SCHEMA_KIND_COUNT}
        className="w-full"
        end={
          <ToggleGroup items={toggles} active={active} onSelect={onSelect} label="Schema views" />
        }
      />
      {children}
    </Content.Card>
  );
}

export function NodeDiffStandIn() {
  return (
    <Col className="gap-2 p-3">
      <h3 className="font-semibold text-sm">Schema nodes changed on this branch</h3>
      <ul className="divide-y rounded-lg border text-sm">
        {[
          ["SchemaNode", "InfraDevice", "updated", "1 attribute added"],
          ["SchemaNode", "LocationSite", "updated", "2 attributes changed"],
          ["SchemaNode", "InfraCircuit", "updated", "2 attributes added, 1 removed, 1 changed"],
          ["SchemaGeneric", "DcimGenericDevice", "updated", "1 attribute added"],
          ["SchemaNode", "LocationRack", "updated", "1 attribute changed"],
          ["SchemaNode", "InfraBGPSession", "updated", "1 relationship added"],
        ].map(([type, kind, status, detail]) => (
          <li key={kind} className="flex items-center gap-3 px-3 py-2">
            <Badge variant="blue-outline">{status}</Badge>
            <span className="text-foreground-muted">{type}</span>
            <span className="font-medium">{kind}</span>
            <span className="ml-auto text-foreground-muted">{detail}</span>
          </li>
        ))}
      </ul>
      <p className="text-foreground-muted text-xs">
        Stand-in for the existing node diff of the Schema namespace; unchanged in every direction.
      </p>
    </Col>
  );
}

/* ------------------------------------------------------------------ shared inner views */

export const INHERITED_BY: Record<string, string[]> = {
  InfraInterface: ["InfraInterfaceL2", "InfraInterfaceL3"],
  DcimGenericDevice: ["DcimCloudDevice", "DcimPhysicalDevice"],
};

const kindsFor = (kind: string) => {
  const nodes = [kind, ...(INHERITED_BY[kind] ?? [])];
  return [...nodes, ...nodes.map((k) => `Profile${k}`)];
};

export function migrationsForOperation(op: Operation, migrations: Migration[]) {
  if (op.op === "node_remove" || op.op === "node_add" || op.op === "node_prop")
    return migrations.filter((m) => m.path === op.kind);
  const field = op.op === "el_prop" && op.prop === "name" ? op.before : op.name;
  const paths = new Set(kindsFor(op.kind).map((k) => `${k}.${field}`));
  return migrations.filter(
    (m) =>
      paths.has(m.path) ||
      (op.op === "el_prop" &&
        op.prop === "unique" &&
        m.name === "node.uniqueness_constraints.update" &&
        m.path === op.kind)
  );
}

export function unmatchedMigrations(operations: Operation[], migrations: Migration[]) {
  const matched = new Set(operations.flatMap((op) => migrationsForOperation(op, migrations)));
  return migrations.filter((m) => !matched.has(m));
}

export function Stat({
  label,
  value,
  tone,
  hint,
}: {
  label: ReactNode;
  value: ReactNode;
  tone?: "danger";
  hint?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 rounded-lg border bg-content px-3 py-2">
      <span className="text-foreground-muted text-xs">{label}</span>
      <span
        className={classNames(
          "font-semibold text-lg tabular-nums",
          tone === "danger" && "text-danger"
        )}
      >
        {value}
      </span>
      {hint && <span className="text-foreground-muted text-xs">{hint}</span>}
    </div>
  );
}

export function StagedSummary({ change, impact }: { change: SchemaChange; impact: Impact }) {
  if (impact.status !== "done") return null;
  const kinds = new Set(impact.migrations.map((m) => m.path.split(".")[0]));
  const deleted = deletionTotals(impact.migrations);
  const hidden = sum(impact.denied.map((d) => d.count));
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
      <Stat label="Operations" value={fmt(change.operations.length)} />
      <Stat
        label="Migrations"
        value={fmt(impact.migrations.length)}
        hint={`on ${kinds.size} kinds`}
      />
      <Stat label="Nodes touched" value={fmt(sum(impact.migrations.map((m) => m.nodes)))} />
      <Stat
        label="Nodes that would fail"
        value={fmt(impact.violations.length + hidden)}
        tone="danger"
        hint={hidden ? `${fmt(hidden)} you cannot view` : undefined}
      />
      <Stat
        label="Data deleted"
        value={fmt(deleted.nodes + deleted.values + deleted.peers)}
        tone="danger"
        hint={`${fmt(deleted.nodes)} nodes · ${fmt(deleted.values)} values · ${fmt(deleted.peers)} peers`}
      />
    </div>
  );
}

export function ImpactStatus({ impact, compact }: { impact: Impact; compact?: boolean }) {
  const recalc = (
    <button
      type="button"
      className="flex items-center gap-1 rounded-md border bg-content px-2 py-1 text-sm hover:bg-content-strong"
    >
      <Icon icon="mdi:refresh" aria-hidden="true" />
      Recalculate
    </button>
  );
  if (impact.status === "running")
    return (
      <InlineMessage tone="info" title="Calculating the impact on this branch">
        Started 1 minute ago. The counts and the nodes that would fail appear when it ends.
      </InlineMessage>
    );
  if (impact.status === "failed")
    return (
      <InlineMessage tone="danger" title="The impact could not be calculated" action={recalc}>
        {impact.error}
      </InlineMessage>
    );
  if (impact.conflicts.length)
    return (
      <InlineMessage tone="danger" title="The staged schema no longer matches the branch schema">
        <ul className="list-disc pl-4">
          {impact.conflicts.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        Fix the schema file and stage it again.
      </InlineMessage>
    );
  if (impact.outOfDate)
    return (
      <InlineMessage
        tone="warning"
        title="The branch schema changed after the impact was calculated"
        action={recalc}
      >
        Calculated <When date={impact.calculatedAt} />. Recalculate before you apply.
      </InlineMessage>
    );
  return (
    <Row className="flex-wrap items-center gap-2 text-foreground-muted text-sm">
      <span>
        Impact calculated <When date={impact.calculatedAt} />
        {!compact && ". Infrahub does not recalculate it when data changes on the branch."}
      </span>
      {recalc}
    </Row>
  );
}

const STAGED_DELETED = deletionTotals(STAGED_MIGRATIONS);

export function StagedActions({ blocked }: { blocked?: boolean }) {
  const [confirm, setConfirm] = useState<"apply" | "discard" | null>(null);
  return (
    <Row className="gap-2">
      <Button variant="outline" size="sm" onPress={() => setConfirm("discard")}>
        Discard
      </Button>
      <Button size="sm" isDisabled={blocked} onPress={() => setConfirm("apply")}>
        Apply to branch
      </Button>
      <ModalConfirm
        isOpen={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm === "apply"
            ? "Apply the staged schema change?"
            : "Discard the staged schema change?"
        }
        description={
          confirm === "apply"
            ? `Infrahub recalculates the impact, then runs ${STAGED_MIGRATIONS.length} migrations on ${fmt(sum(STAGED_MIGRATIONS.map((m) => m.nodes)))} nodes. It deletes ${fmt(STAGED_DELETED.nodes)} nodes, ${fmt(STAGED_DELETED.values)} attribute values and ${fmt(STAGED_DELETED.peers)} peers. If a node fails a check, nothing is applied and the change stays staged.`
            : "The staged schema change and its impact are deleted. The branch schema and data do not change."
        }
        confirmLabel={confirm === "apply" ? "Apply" : "Discard"}
        onConfirm={() => setConfirm(null)}
      />
    </Row>
  );
}

export function DifferenceView({ change, impact }: { change: SchemaChange; impact: Impact }) {
  const byKind = new Map<string, Operation[]>();
  for (const op of change.operations) byKind.set(op.kind, [...(byKind.get(op.kind) ?? []), op]);
  const extra = unmatchedMigrations(change.operations, impact.migrations);
  const failing = (path: string) =>
    impact.violations.filter((v) => v.path === path).length +
    sum(impact.denied.filter((d) => d.path === path).map((d) => d.count));
  return (
    <Col className="gap-3">
      {[...byKind.entries()].map(([kind, ops]) => (
        <section key={kind} aria-label={kind} className="rounded-lg border">
          <h4 className="border-b bg-content px-3 py-1.5 font-semibold text-sm">{kind}</h4>
          <ul className="divide-y">
            {ops.map((op, i) => {
              const ms = migrationsForOperation(op, impact.migrations);
              return (
                <li
                  key={i}
                  className="flex flex-wrap items-start gap-x-4 gap-y-1 px-3 py-2 text-sm"
                >
                  <span className="min-w-0 grow">
                    <OperationText op={op} />
                  </span>
                  {ms.length === 0 ? (
                    <span className="text-foreground-muted text-xs">No migration</span>
                  ) : (
                    ms.map((m) => (
                      <span
                        key={`${m.name}:${m.path}`}
                        className="flex shrink-0 flex-wrap gap-2 text-xs"
                      >
                        {(m.path.split(".")[0] !== op.kind || m.path === op.kind) &&
                          op.op.startsWith("el_") && (
                            <Tooltip message={<Mono>{m.name}</Mono>}>
                              <span className="text-foreground-muted">{m.path.split(".")[0]}</span>
                            </Tooltip>
                          )}
                        <span className="tabular-nums">{fmt(m.nodes)} nodes</span>
                        {m.deletes && (
                          <span className="text-danger tabular-nums">
                            deletes {fmt(m.deletes.count)} {m.deletes.what}
                          </span>
                        )}
                        {failing(m.path) > 0 && (
                          <span className="text-danger tabular-nums">
                            {fmt(failing(m.path))} would fail
                          </span>
                        )}
                      </span>
                    ))
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {extra.length > 0 && (
        <section aria-label="Migrations Infrahub adds" className="rounded-lg border border-dashed">
          <h4 className="border-b border-dashed px-3 py-1.5 font-semibold text-sm">
            Migrations Infrahub adds
            <span className="ml-2 font-normal text-foreground-muted">
              on kinds that inherit a changed generic, on profiles, and from uniqueness constraints
            </span>
          </h4>
          <MigrationTable migrations={extra} mode="impact" caption="Migrations Infrahub adds" />
        </section>
      )}
    </Col>
  );
}

export function RevisionLine({
  branch,
  history,
  staged,
  running,
}: {
  branch: string;
  history: SchemaChange[];
  staged?: SchemaChange;
  running?: boolean;
}) {
  const last = revisionOf(history);
  const failed = history.filter((c) => c.status === "failed").length;
  return (
    <Row className="flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span className="text-foreground-muted">Schema revision of {branch}</span>
      {last && (
        <>
          <span className="rounded-md bg-content-strong px-1.5 py-0.5 font-mono font-semibold text-xs tabular-nums">
            {pad(last.version ?? 0)}
          </span>
          <Mono className="text-foreground">{last.name}</Mono>
          <span className="text-foreground-muted">
            applied <When date={last.appliedAt ?? last.createdAt} />
          </span>
        </>
      )}
      {failed > 0 && (
        <Badge variant="red">
          {failed} failed load{failed > 1 ? "s" : ""}
        </Badge>
      )}
      {staged && !running && (
        <Badge variant="blue" className="gap-1">
          <Icon icon="mdi:tray-arrow-down" aria-hidden="true" />1 staged schema change pending
        </Badge>
      )}
      {running && (
        <Badge variant="yellow" className="gap-1">
          <Icon icon="mdi:progress-clock" aria-hidden="true" />
          Applying the staged schema change
        </Badge>
      )}
    </Row>
  );
}

export function ApplicationRow({ app, index }: { app: Application; index: number }) {
  const [open, setOpen] = useState(app.status === "failed");
  const deleted = deletionTotals(app.migrations);
  return (
    <li className="rounded-md border">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-2 py-1.5 text-left text-sm hover:bg-content"
      >
        <Icon icon={open ? "mdi:chevron-down" : "mdi:chevron-right"} aria-hidden="true" />
        <span className="font-medium">Run {index + 1}</span>
        <When date={app.at} />
        <StatusBadge status={app.status} level="application" />
        <span className="text-foreground-muted">
          {app.migrations.length} migration{app.migrations.length === 1 ? "" : "s"}
        </span>
        {deleted.values + deleted.nodes + deleted.peers > 0 && (
          <span className="text-danger text-xs">
            deleted {fmt(deleted.nodes + deleted.values + deleted.peers)}
          </span>
        )}
      </button>
      {open && (
        <div className="border-t">
          {app.error && <p className="px-3 py-1.5 text-danger text-sm">{app.error}</p>}
          <MigrationTable
            migrations={app.migrations}
            mode="run"
            caption={`Migrations of run ${index + 1}`}
          />
        </div>
      )}
    </li>
  );
}

export function opsSummary(change: SchemaChange) {
  const [first, ...rest] = change.operations;
  if (!first) return "No operation";
  return rest.length ? (
    <>
      <OperationText op={first} />
      <span className="text-foreground-muted"> and {rest.length} more</span>
    </>
  ) : (
    <OperationText op={first} />
  );
}

export function HistoryRow({
  change,
  defaultOpen,
}: {
  change: SchemaChange;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(!!defaultOpen);
  const last = change.applications.at(-1);
  return (
    <li className="border-b last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-start gap-x-3 px-3 py-2 text-left hover:bg-content"
      >
        <Icon
          icon={open ? "mdi:chevron-down" : "mdi:chevron-right"}
          className="mt-0.5"
          aria-hidden="true"
        />
        <span className="w-14 rounded-md bg-content-strong px-1.5 py-0.5 text-center font-mono font-semibold text-xs tabular-nums">
          {change.version === null ? "—" : pad(change.version)}
        </span>
        <span className="min-w-0 grow">
          <Mono className="block truncate font-medium text-foreground text-sm">{change.name}</Mono>
          <span className="block truncate text-foreground-muted text-sm">{opsSummary(change)}</span>
        </span>
        <span className="flex flex-col items-end gap-1 text-foreground-muted text-xs">
          <span className="flex items-center gap-2">
            {change.fromUpgrade && <Badge variant="purple">Before the upgrade</Badge>}
            {change.status !== "applied" && <StatusBadge status={change.status} level="change" />}
            {last && last.status !== "applied" && change.status === "applied" && (
              <StatusBadge status={last.status} level="application" />
            )}
          </span>
          <span>
            {change.status === "failed" ? "loaded" : "applied"}{" "}
            <When date={change.appliedAt ?? change.createdAt} />
            {change.applications.length > 1 && ` · ran ${change.applications.length} times`}
          </span>
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-3 border-t bg-content/40 px-3 py-3 pl-12">
          {change.fromUpgrade && (
            <p className="text-foreground-muted text-sm">
              Every load made before the upgrade to this version is combined in this schema change.
              Their order is not known.
            </p>
          )}
          <OperationList operations={change.operations} limit={6} />
          {change.parent && (
            <span className="text-foreground-muted text-xs">
              Parent <Mono>{change.parent}</Mono>
            </span>
          )}
          <ul className="flex flex-col gap-1">
            {change.applications.map((app, i) => (
              <ApplicationRow key={app.at} app={app} index={i} />
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

export function HistoryList({
  history,
  openId,
  newestFirst = true,
}: {
  history: SchemaChange[];
  openId?: string;
  newestFirst?: boolean;
}) {
  const appliedChanges = history
    .filter((c) => c.status !== "failed")
    .sort((a, b) => (newestFirst ? -1 : 1) * ((a.version ?? 0) - (b.version ?? 0)));
  const failed = history.filter((c) => c.status === "failed");
  return (
    <Col className="gap-3">
      {failed.length > 0 && (
        <section aria-label="Failed loads" className="rounded-lg border border-danger/40">
          <h3 className="flex items-center gap-2 border-b px-3 py-1.5 font-semibold text-sm">
            Failed loads
            <Badge variant="red">{failed.length}</Badge>
            <span className="font-normal text-foreground-muted">
              They changed nothing and have no version. Listed by the time they were loaded.
            </span>
          </h3>
          <ul>
            {failed.map((c) => (
              <HistoryRow key={c.id} change={c} defaultOpen={c.id === openId} />
            ))}
          </ul>
        </section>
      )}
      <section aria-label="Applied schema changes" className="rounded-lg border">
        <h3 className="flex items-center gap-2 border-b px-3 py-1.5 font-semibold text-sm">
          Applied schema changes
          <Badge>{appliedChanges.length}</Badge>
        </h3>
        <ul>
          {appliedChanges.map((c) => (
            <HistoryRow key={c.id} change={c} defaultOpen={c.id === openId} />
          ))}
        </ul>
      </section>
    </Col>
  );
}

export function RunProgress({ app, change }: { app: Application; change: SchemaChange }) {
  const ended = app.migrations.filter(
    (m) => m.status === "applied" || m.status === "failed"
  ).length;
  return (
    <Col className="gap-3">
      <Row className="flex-wrap items-center gap-x-3 gap-y-1">
        <StatusBadge status="running" />
        <span className="font-medium text-sm">
          Applying <Mono>{change.name}</Mono>
        </span>
        <span className="text-foreground-muted text-sm">
          started <When date={app.at} />
        </span>
      </Row>
      <Meter
        label={`${ended} of ${app.migrations.length} migrations ended`}
        value={ended}
        maxValue={app.migrations.length}
      />
      <MigrationTable migrations={app.migrations} mode="run" caption="Migrations of this run" />
    </Col>
  );
}

export function ReplayList({ mode }: { mode: "review" | "rolled back" }) {
  const [open, setOpen] = useState<string | null>(PC_CHECK.failingChangeId);
  const steps = PROPOSED_CHANGE.replay;
  const failIndex = steps.findIndex((c) => c.id === PC_CHECK.failingChangeId);
  return (
    <ol className="rounded-lg border">
      {steps.map((c, i) => {
        const onMain = PROPOSED_CHANGE.mainVersion + i + 1;
        const status =
          mode === "rolled back"
            ? (MERGE_ATTEMPT.applications[i]?.status ?? "not run")
            : i < failIndex
              ? "applied"
              : i === failIndex
                ? "failed"
                : "not run";
        const isOpen = open === c.id;
        return (
          <li key={c.id} className="border-b last:border-b-0">
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : c.id)}
              className="flex w-full items-start gap-x-3 px-3 py-2 text-left hover:bg-content"
            >
              <span className="mt-0.5 w-6 text-right text-foreground-muted text-sm tabular-nums">
                {i + 1}
              </span>
              <span className="flex items-center gap-1 font-mono text-xs tabular-nums">
                <span className="rounded-md bg-content-strong px-1.5 py-0.5">
                  {pad(c.version ?? 0)}
                </span>
                <Icon icon="mdi:arrow-right" aria-label="becomes on main" />
                <span className="rounded-md bg-content-strong px-1.5 py-0.5 font-semibold">
                  {pad(onMain)}
                </span>
              </span>
              <span className="min-w-0 grow">
                <Mono className="block truncate font-medium text-foreground text-sm">{c.name}</Mono>
                <span className="block truncate text-foreground-muted text-sm">
                  {opsSummary(c)}
                </span>
              </span>
              <span className="flex items-center gap-2">
                {mode === "review" ? (
                  status === "failed" ? (
                    <Badge variant="red" className="gap-1">
                      <Icon icon="mdi:close-circle-outline" aria-hidden="true" />
                      Would fail
                    </Badge>
                  ) : status === "applied" ? (
                    <Badge variant="green" className="gap-1">
                      <Icon icon="mdi:check" aria-hidden="true" />
                      Passes
                    </Badge>
                  ) : (
                    <Badge variant="gray-outline">Not checked</Badge>
                  )
                ) : (
                  <StatusBadge status={status} level="application" />
                )}
              </span>
            </button>
            {isOpen && (
              <div className="flex flex-col gap-3 border-t bg-content/40 px-3 py-3 pl-12">
                {status === "failed" && (
                  <InlineMessage
                    tone="danger"
                    title={
                      mode === "review"
                        ? "This step would fail against the current main"
                        : "This step failed"
                    }
                  >
                    {mode === "review" ? PC_CHECK.message : MERGE_ATTEMPT.error}
                  </InlineMessage>
                )}
                <OperationList operations={c.operations} limit={6} />
                {status === "failed" && <ViolationList violations={PC_CHECK.violations} />}
                <MigrationTable
                  migrations={c.applications.at(-1)?.migrations ?? []}
                  mode="impact"
                  caption="Migrations on the branch"
                />
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
