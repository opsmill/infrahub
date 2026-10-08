// PROTO number-pool — fake schema and the "scoped by" field shared by the create and edit sheets. Delete with the prototype.
import { Autocomplete, Button, ListBox, Popover, SelectItem, Tooltip } from "@infrahub/ui";
import { PlusIcon, TriangleAlertIcon, XIcon } from "lucide-react";
import React from "react";
import { Button as AriaButton, DialogTrigger, Header, ListBoxSection } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

type NumberAttribute = { name: string; unique: boolean; min: number; max: number };

// a scope entry must be required; optional, list and JSON fields are listed but can't be picked
type ScopeCandidate = {
  name: string;
  label: string;
  type: "relationship" | "attribute";
  detail: string;
  unavailable?: string;
};

export type KindSchema = {
  kind: string;
  label: string;
  numberAttributes: NumberAttribute[];
  scopeCandidates: ScopeCandidate[];
};

const rel = (name: string, label: string, peer: string, unavailable?: string): ScopeCandidate => ({
  name,
  label,
  type: "relationship",
  detail: peer,
  unavailable,
});
const attr = (name: string, label: string, kind: string, unavailable?: string): ScopeCandidate => ({
  name,
  label,
  type: "attribute",
  detail: kind,
  unavailable,
});

export const KINDS: KindSchema[] = [
  {
    kind: "InfraSubinterface",
    label: "Subinterface",
    numberAttributes: [
      { name: "unit_id", unique: false, min: 0, max: 16_383 },
      { name: "vlan_id", unique: false, min: 1, max: 4094 },
      { name: "mtu", unique: false, min: 68, max: 9216 },
    ],
    scopeCandidates: [
      rel("device", "Device", "InfraDevice"),
      rel("vrf", "VRF", "IpamVRF"),
      rel("status", "Status", "BuiltinStatus"),
      rel("parent_interface", "Parent interface", "InfraInterfaceL3", "Optional"),
      rel("untagged_vlan", "Untagged VLAN", "InfraVLAN", "Optional"),
      attr("encapsulation", "Encapsulation", "Dropdown"),
      attr("description", "Description", "Text", "Optional"),
      attr("tags_list", "Tag names", "List", "List attributes can't be used"),
    ],
  },
  {
    kind: "InfraCircuit",
    label: "Circuit",
    numberAttributes: [
      { name: "circuit_number", unique: true, min: 1, max: 99_999 },
      { name: "legacy_id", unique: true, min: 1, max: 99_999 },
      { name: "bandwidth", unique: false, min: 1, max: 400_000 },
    ],
    scopeCandidates: [
      rel("provider", "Provider", "OrganizationProvider"),
      rel("site", "Site", "LocationSite"),
      attr("circuit_type", "Circuit type", "Dropdown"),
    ],
  },
  {
    kind: "InfraAutonomousSystem",
    label: "Autonomous System",
    numberAttributes: [{ name: "asn", unique: true, min: 1, max: 4_294_967_294 }],
    scopeCandidates: [rel("organization", "Organization", "OrganizationGeneric")],
  },
  {
    kind: "InfraDevice",
    label: "Device",
    numberAttributes: [
      { name: "loopback_id", unique: true, min: 0, max: 4095 },
      { name: "rack_position", unique: false, min: 1, max: 48 },
    ],
    scopeCandidates: [
      rel("site", "Site", "LocationSite"),
      rel("platform", "Platform", "InfraPlatform"),
      rel("status", "Status", "BuiltinStatus"),
      rel("role", "Role", "BuiltinRole"),
      rel("rack", "Rack", "LocationRack", "Optional"),
      rel(
        "management_vrf_for_out_of_band_access",
        "Management VRF for out-of-band access",
        "IpamVRF",
        "Optional"
      ),
      attr("os_version", "OS version", "Text", "Optional"),
    ],
  },
  {
    kind: "InfraVLAN",
    label: "VLAN",
    numberAttributes: [{ name: "vlan_id", unique: false, min: 1, max: 4094 }],
    scopeCandidates: [
      rel("site", "Site", "LocationSite"),
      rel("l2_domain", "L2 domain", "InfraL2Domain", "Optional"),
      attr("role", "Role", "Dropdown"),
      attr("status", "Status", "Dropdown"),
      attr("description", "Description", "Text", "Optional"),
    ],
  },
];

export const findKind = (kind: string | null) => KINDS.find((k) => k.kind === kind) ?? null;

const emptyChip =
  "inline-flex h-7 items-center gap-1 rounded-lg border border-border-strong border-dashed px-2 text-foreground-muted text-sm outline-none transition-colors duration-150 data-hovered:bg-highlight data-hovered:text-foreground focus-visible:ring-2 focus-visible:ring-ring-halo data-disabled:opacity-60";

const EMPTY_TOOLTIP =
  "Every object shares one sequence. Click to give each related object or value its own sequence.";

function CandidatePicker({
  schema,
  scope,
  onAdd,
  isOpen,
  onOpenChange,
  trigger,
}: {
  schema: KindSchema;
  scope: string[];
  onAdd: (name: string) => void;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  trigger: React.ReactNode;
}) {
  const remaining = schema.scopeCandidates.filter((c) => !scope.includes(c.name));
  const sections = [
    {
      id: "relationship",
      title: "Relationships",
      items: remaining.filter((c) => c.type === "relationship"),
    },
    {
      id: "attribute",
      title: "Attributes",
      items: remaining.filter((c) => c.type === "attribute"),
    },
  ].filter((section) => section.items.length > 0);
  const disabledKeys = remaining.filter((c) => c.unavailable).map((c) => c.name);

  return (
    <DialogTrigger isOpen={isOpen} onOpenChange={onOpenChange}>
      {trigger}
      <Popover placement="bottom start" className="w-80">
        <Autocomplete>
          <ListBox
            aria-label="Scope fields"
            items={sections}
            disabledKeys={disabledKeys}
            className="max-h-80"
            onAction={(key) => {
              onAdd(String(key));
              onOpenChange(false);
            }}
          >
            {(section) => (
              <ListBoxSection id={section.id}>
                <Header className="px-2 pt-2 pb-1 font-medium text-foreground-muted text-xs">
                  {section.title}
                </Header>
                {section.items.map((c) => (
                  <SelectItem key={c.name} id={c.name} textValue={c.label}>
                    <span className="flex w-full items-baseline gap-2">
                      <span className="min-w-0 flex-1 truncate">{c.label}</span>
                      <span className="shrink-0 text-foreground-muted text-xs">
                        {c.unavailable ?? <span className="font-mono">{c.detail}</span>}
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </ListBoxSection>
            )}
          </ListBox>
        </Autocomplete>
      </Popover>
    </DialogTrigger>
  );
}

export function ScopeField({
  schema,
  scope,
  setScope,
}: {
  schema: KindSchema | null;
  scope: string[];
  setScope: (scope: string[]) => void;
}) {
  const [isOpen, setIsOpen] = React.useState(false);
  const labelOf = (name: string) =>
    schema?.scopeCandidates.find((c) => c.name === name)?.label ?? name;
  const add = (name: string) => setScope([...scope, name]);

  if (!schema) {
    return (
      <AriaButton isDisabled className={emptyChip}>
        No relationship or attribute
      </AriaButton>
    );
  }

  if (scope.length === 0) {
    return (
      <CandidatePicker
        schema={schema}
        scope={scope}
        onAdd={add}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        trigger={
          <Tooltip message={EMPTY_TOOLTIP}>
            <AriaButton className={classNames(emptyChip, "self-start")}>
              No relationship or attribute
            </AriaButton>
          </Tooltip>
        }
      />
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {scope.map((name, i) => (
        <React.Fragment key={name}>
          {i > 0 && <span className="text-foreground-muted">+</span>}
          <span className="inline-flex h-7 max-w-full items-center gap-1 rounded-lg border border-border-strong bg-card pr-0.5 pl-2 text-sm">
            <span className="truncate">{labelOf(name)}</span>
            <Button
              variant="ghost"
              shape="square"
              size="xxs"
              aria-label={`Remove ${labelOf(name)}`}
              onPress={() => setScope(scope.filter((n) => n !== name))}
              className="text-foreground-muted"
            >
              <XIcon />
            </Button>
          </span>
        </React.Fragment>
      ))}
      <CandidatePicker
        schema={schema}
        scope={scope}
        onAdd={add}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        trigger={
          <Button
            variant="ghost"
            size="sm"
            shape="square"
            aria-label="Add a relationship or attribute"
          >
            <PlusIcon />
          </Button>
        }
      />
    </div>
  );
}

export function WarningNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex gap-2 text-pretty rounded-lg border border-warning-border bg-warning-surface px-2.5 py-2 text-sm text-warning">
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
