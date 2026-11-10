// PROTOTYPE design-jam schema-viewer-sections
// Stand-in for the /schema page and the viewer panel; revisions copy from it and never edit it.
import { Button } from "@infrahub/ui";
import { parseAsString, useQueryState } from "nuqs";
import type { ReactNode } from "react";
import { TabList, Tabs } from "react-aria-components";

import { Icon } from "@/shared/components/display/icon";
import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { isRelationshipVisibleInSummary } from "@/entities/nodes/object/domain/rules/is-relationship-visible-in-summary";
import type {
  AttributeSchema,
  ContainerSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { TabPanelStyled, TabStyled } from "@/entities/schema/ui/styled";

import fixtures from "./fixtures.json";

const BIG_KIND = "InfraOpticalTransceiverLifecycleAssignment";

function buildBigNode(): ModelSchema {
  const template = (fixtures as Record<string, any>).InfraInterface.attributes.find(
    (a: AttributeSchema) => a.name === "description"
  );
  const attr = (
    name: string,
    label: string,
    container: string | null,
    weight: number,
    kind = "Text"
  ) => ({
    ...template,
    id: `proto-${name}`,
    name,
    label,
    kind,
    container,
    inherited: false,
    optional: true,
    description: null,
    order_weight: weight,
  });
  const optics = [
    ["wavelength_nm", "Wavelength (nm)", "Number"],
    ["form_factor", "Form factor"],
    ["reach_km", "Reach (km)", "Number"],
    ["connector_type", "Connector type"],
    ["tx_power_min_dbm", "Transmit power minimum (dBm)", "Number"],
    ["tx_power_max_dbm", "Transmit power maximum (dBm)", "Number"],
    ["rx_sensitivity_dbm", "Receive sensitivity (dBm)", "Number"],
    ["fiber_mode", "Fiber mode"],
    ["dom_supported", "Digital optical monitoring", "Boolean"],
    ["coding_profile", "Vendor coding profile"],
    ["breakout_mode", "Breakout mode"],
    ["temperature_range", "Temperature range"],
    ["laser_class", "Laser safety class"],
    ["dispersion_tolerance", "Chromatic dispersion tolerance (ps/nm)", "Number"],
  ];
  const details = [
    ["name", "Name"],
    ["serial_number", "Serial number"],
    ["part_number", "Manufacturer part number"],
    ["status", "Status"],
    ["role", "Role"],
    ["slot", "Slot"],
    ["port_label", "Port label as printed on the faceplate"],
    ["asset_tag", "Asset tag"],
    ["installed_at", "Installed at", "DateTime"],
    ["description", "Description"],
  ];
  const procurement = [
    ["purchase_order", "Purchase order"],
    ["invoice_reference", "Invoice reference"],
    ["unit_cost", "Unit cost", "Number"],
    ["warranty_end", "Warranty end", "DateTime"],
    ["support_contract", "Support contract"],
    ["reseller", "Reseller"],
  ];
  const advanced = [
    ["raw_eeprom", "Raw EEPROM dump", "TextArea"],
    ["firmware_revision", "Firmware revision"],
    ["last_polled_at", "Last polled at", "DateTime"],
  ];
  let weight = 1000;
  const next = () => {
    weight += 100;
    return weight;
  };
  const attributes = [
    ...details.map(([n, l, k]) => attr(n!, l!, null, next(), k)),
    ...optics.map(([n, l, k]) => attr(n!, l!, "optics", next(), k)),
    attr("end_of_support", "End of support", "lifecycle", next(), "DateTime"),
    ...procurement.map(([n, l, k]) => attr(n!, l!, "procurement", next(), k)),
    ...advanced.map(([n, l, k]) => attr(n!, l!, "advanced", next(), k)),
  ];
  const relTemplate = (fixtures as Record<string, any>).InfraLagInterfaceL2.relationships.find(
    (r: RelationshipSchema) => r.name === "device"
  );
  const rel = (
    name: string,
    label: string,
    peer: string,
    container: string | null,
    cardinality: "one" | "many",
    kind: string
  ) => ({
    ...relTemplate,
    id: `proto-${name}`,
    name,
    label,
    peer,
    container,
    cardinality,
    kind,
    inherited: false,
    order_weight: next(),
  });

  return {
    ...(fixtures as Record<string, any>).ExampleSite,
    id: "proto-big-node",
    namespace: "Infra",
    name: "OpticalTransceiverLifecycleAssignment",
    kind: BIG_KIND,
    label: "Optical Transceiver Lifecycle Assignment",
    description:
      "Tracks one pluggable optic from purchase to end of support, per device port and spare pool.",
    icon: "mdi:expansion-card-variant",
    inherit_from: [],
    containers: [
      {
        name: "optics",
        label: "Optics",
        description: "Optical characteristics read from the vendor datasheet",
        order_weight: 100,
        collapsed: false,
        inherited: false,
      },
      {
        name: "lifecycle",
        label: "Lifecycle and end-of-support tracking",
        description: null,
        order_weight: 200,
        collapsed: false,
        inherited: false,
      },
      {
        name: "procurement",
        label: "Procurement",
        description: "Purchase, warranty and support contract",
        order_weight: 300,
        collapsed: true,
        inherited: false,
      },
    ],
    attributes,
    relationships: [
      rel("device", "Device", "DcimDevice", null, "one", "Parent"),
      rel("site", "Site", "LocationSite", null, "one", "Attribute"),
      rel("vendor", "Vendor", "OrganizationManufacturer", "procurement", "one", "Attribute"),
      rel("spare_pool", "Spare pool", "InventorySparePool", "procurement", "many", "Generic"),
    ],
  } as ModelSchema;
}

export const SCHEMAS: Record<string, ModelSchema> = {
  ...(fixtures as unknown as Record<string, ModelSchema>),
  [BIG_KIND]: buildBigNode(),
};

export const TEST_KINDS = [
  "InfraLagInterfaceL2",
  "InfraLagInterface",
  "InfraLagInterfaceL3",
  BIG_KIND,
  "ExampleSite",
  "TemplateInfraLagInterface",
  "CoreAccount",
];

export type Source =
  | { type: "own" }
  | { type: "builtin" }
  | { type: "inherited"; from: string }
  | { type: "redeclared"; from: string };

const parentsOf = (schema: ModelSchema): ModelSchema[] =>
  ("inherit_from" in schema ? (schema.inherit_from ?? []) : [])
    .map((kind) => SCHEMAS[kind])
    .filter((s): s is ModelSchema => !!s);

export function fieldSource(
  schema: ModelSchema,
  field: AttributeSchema | RelationshipSchema
): Source {
  const declaring = parentsOf(schema).find((parent) =>
    [...(parent.attributes ?? []), ...(parent.relationships ?? [])].some(
      (f) => f.name === field.name
    )
  );
  if (!declaring) return { type: "own" };
  return field.inherited
    ? { type: "inherited", from: declaring.kind! }
    : { type: "redeclared", from: declaring.kind! };
}

export function sectionSource(schema: ModelSchema, container: ContainerSchema): Source {
  if (!container.inherited) return { type: "own" };
  const declaring = parentsOf(schema).find((parent) =>
    ("containers" in parent ? (parent.containers ?? []) : []).some((c) => c.name === container.name)
  );
  return declaring ? { type: "inherited", from: declaring.kind! } : { type: "own" };
}

export type ViewerSection = {
  name: string;
  label: string;
  description?: string | null;
  collapsed: boolean;
  orderWeight?: number | null;
  source: Source;
  attributes: AttributeSchema[];
  relationships: RelationshipSchema[];
};

const byWeight = <T extends { order_weight?: number | null }>(items: T[]) =>
  [...items].sort((a, b) => (a.order_weight ?? 0) - (b.order_weight ?? 0));

/** Same order as the detail page, but declared sections stay even when empty on this kind. */
export function viewerSections(schema: ModelSchema): ViewerSection[] {
  const containers = "containers" in schema ? (schema.containers ?? []) : [];
  const attributes = byWeight(schema.attributes ?? []);
  const relationships = byWeight(schema.relationships ?? []);
  const usesAdvanced = [...attributes, ...relationships].some((f) => f.container === "advanced");
  if (containers.length === 0 && !usesAdvanced) return [];

  const declared = byWeight(containers).map((c) => c.name);
  const sectionOf = (f: { container?: string | null }) =>
    f.container === "advanced"
      ? "advanced"
      : declared.includes(f.container ?? "")
        ? f.container!
        : "details";
  const make = (
    name: string,
    label: string,
    rest: Partial<ViewerSection> & { source: Source }
  ): ViewerSection => ({
    name,
    label,
    collapsed: false,
    attributes: attributes.filter((f) => sectionOf(f) === name),
    relationships: relationships.filter((f) => sectionOf(f) === name),
    ...rest,
  });

  const sections = [
    make("details", "Details", { source: { type: "builtin" } }),
    ...byWeight(containers).map((c) =>
      make(c.name, c.label ?? c.name, {
        description: c.description,
        collapsed: !!c.collapsed,
        orderWeight: c.order_weight,
        source: sectionSource(schema, c),
      })
    ),
    make("advanced", "Advanced", { collapsed: true, source: { type: "builtin" } }),
  ];
  return sections.filter(
    (s) => s.source.type !== "builtin" || s.attributes.length > 0 || s.relationships.length > 0
  );
}

/** Relationships the detail page leaves out of its section cards. */
export const isShownAsTab = (relationship: RelationshipSchema) =>
  !isRelationshipVisibleInSummary(relationship);

export function SourceTag({
  source,
  onKindClick,
}: {
  source: Source;
  onKindClick?: (kind: string) => void;
}) {
  if (source.type === "own") return null;
  if (source.type === "builtin")
    return <span className="font-normal text-foreground-muted text-xs">built in</span>;
  const prefix = source.type === "inherited" ? "from" : "redeclared, from";
  return (
    <span className="inline-flex items-center gap-1 font-normal text-foreground-muted text-xs">
      {prefix}
      <button
        type="button"
        className="rounded-sm text-custom-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-ring dark:text-custom-blue-300"
        onClick={(e) => {
          e.stopPropagation();
          onKindClick?.(source.from);
        }}
      >
        {source.from}
      </button>
    </span>
  );
}

export function useSelectedKind() {
  return useQueryState("proto.kind", parseAsString.withDefault(TEST_KINDS[0]!));
}

/** The /schema page around the viewer: the kind list on the left, the panel at its real width. */
export function SchemaPage({
  children,
}: {
  children: (schema: ModelSchema, onKindClick: (kind: string) => void) => ReactNode;
}) {
  const [kind, setKind] = useSelectedKind();
  const schema = SCHEMAS[kind] ?? SCHEMAS[TEST_KINDS[0]!]!;

  return (
    <div className="flex h-full grow items-stretch overflow-hidden bg-background">
      <nav className="w-72 shrink-0 space-y-1 overflow-auto border-r p-3" aria-label="Test kinds">
        <p className="px-2 pb-1 font-semibold text-foreground-muted text-xs uppercase tracking-wide">
          Test kinds
        </p>
        {TEST_KINDS.map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKind(k)}
            className={classNames(
              "block w-full truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-highlight focus-visible:outline-2 focus-visible:outline-ring",
              k === schema.kind && "bg-highlight font-semibold"
            )}
          >
            {k}
          </button>
        ))}
      </nav>
      <div className="flex min-w-0 grow justify-end">
        <div className="m-2 flex min-h-0 w-full min-w-96 max-w-xl sm:min-w-130">
          {children(schema, setKind)}
        </div>
      </div>
    </div>
  );
}

export type ViewerTab = { id: string; label: string; content: ReactNode };

export function ViewerPanel({
  schema,
  tabs,
  selectedTab,
  onTabChange,
}: {
  schema: ModelSchema;
  tabs: ViewerTab[];
  selectedTab?: string;
  onTabChange?: (id: string) => void;
}) {
  return (
    <section className="flex w-full flex-col space-y-4 overflow-hidden rounded-md border bg-card p-4 shadow-lg">
      <div className="flex items-start justify-between">
        <div className="space-x-1">
          <Badge variant="blue">{schema.namespace}</Badge>
          <Badge>{isGenericSchema(schema) ? "Generic" : "Node"}</Badge>
          <span className="text-xs">{schema.id}</span>
        </div>
        <Button size="xs" shape="circle" variant="ghost" aria-label="Close schema viewer">
          <Icon icon="mdi:close" className="text-xl" />
        </Button>
      </div>

      <header className="flex gap-2">
        {schema.icon && (
          <Icon
            icon={schema.icon}
            className="self-start rounded-sm border border-accent/20 p-2 text-accent text-xl"
          />
        )}
        <div>
          <h1 className="font-semibold">{schema.label}</h1>
          <p className="text-foreground-muted text-sm">{schema.description}</p>
        </div>
      </header>

      <Tabs
        selectedKey={selectedTab}
        onSelectionChange={(key) => onTabChange?.(String(key))}
        className="flex min-h-0 flex-col overflow-y-hidden"
      >
        <TabList className="flex">
          {tabs.map((tab) => (
            <TabStyled key={tab.id} id={tab.id}>
              {tab.label}
            </TabStyled>
          ))}
        </TabList>
        {tabs.map((tab) => (
          <TabPanelStyled key={tab.id} id={tab.id}>
            {tab.content}
          </TabPanelStyled>
        ))}
      </Tabs>
    </section>
  );
}
