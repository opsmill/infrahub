import { Button, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";
import { ArrowLeftIcon, XIcon } from "lucide-react";
import React from "react";

import type {
  Elevation,
  ElevationItem,
  RackFace,
} from "@/entities/rack-elevation/domain/model/elevation";
import type { RackElevationMapping } from "@/entities/rack-elevation/domain/model/mapping";
import type {
  AttributeUpdate,
  AttributeValue,
  GraphNode,
  SchemaAttribute,
} from "@/entities/rack-elevation/domain/model/schema";
import {
  buildPlacementUpdates,
  buildUnmountUpdates,
  checkPlacement,
} from "@/entities/rack-elevation/domain/rules/placement";
import { getDisplayLabel } from "@/entities/rack-elevation/domain/rules/resolve-path";
import { LabeledInput } from "@/entities/rack-elevation/ui/labeled-input";
import { useRackElevationStore } from "@/entities/rack-elevation/ui/rack-elevation-store";

interface ObjectDetailsProps {
  nodeId: string;
  elevation: Elevation | null;
  mapping: RackElevationMapping | null;
  onOpenNode: (nodeId: string) => void;
  onBack?: () => void;
  onClose: () => void;
}

export function ObjectDetails({
  nodeId,
  elevation,
  mapping,
  onOpenNode,
  onBack,
  onClose,
}: ObjectDetailsProps) {
  const { nodes, schema } = useRackElevationStore();
  const node = nodes[nodeId];
  const schemaKind = node ? schema[node.kind] : undefined;
  if (!node || !schemaKind) return <div className="p-3 text-sm">Object not found.</div>;

  const item = [...(elevation?.placed ?? []), ...(elevation?.unplaced ?? [])].find(
    (candidate) => candidate.node.id === nodeId
  );
  const isRack = elevation?.rack.id === nodeId;

  return (
    <div className="flex flex-col gap-4">
      <SheetHeader
        eyebrow={schemaKind.label}
        title={getDisplayLabel(node, schema)}
        onBack={onBack}
        onClose={onClose}
      />
      {item && elevation && mapping && (
        <PlacementSection
          key={`${item.key}:${item.position}:${item.face}`}
          item={item}
          elevation={elevation}
          mapping={mapping}
        />
      )}
      {isRack && elevation && (
        <MountedObjectsSection elevation={elevation} onOpenNode={onOpenNode} />
      )}
      <AttributesSection
        key={JSON.stringify(node.attributes)}
        node={node}
        attributes={schemaKind.attributes}
      />
      <RelationshipsSection node={node} onOpenNode={onOpenNode} />
    </div>
  );
}

export function SheetHeader({
  eyebrow,
  title,
  onBack,
  onClose,
}: {
  eyebrow: string;
  title: string;
  onBack?: () => void;
  onClose: () => void;
}) {
  return (
    <div className="flex items-start gap-2">
      {onBack && (
        <Button size="xs" shape="square" variant="ghost" aria-label="Back" onPress={onBack}>
          <ArrowLeftIcon />
        </Button>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-foreground-muted text-xs">{eyebrow}</div>
        <h2 className="truncate font-semibold text-lg">{title}</h2>
      </div>
      <Button size="xs" shape="square" variant="ghost" aria-label="Close" onPress={onClose}>
        <XIcon />
      </Button>
    </div>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 rounded-xl border bg-content p-3">
      <h3 className="font-medium text-foreground-muted text-xs uppercase tracking-wide">{title}</h3>
      {children}
    </section>
  );
}

function TargetNote({ target, fallback }: { target: string | null; fallback: string }) {
  return (
    <span className="text-foreground-muted text-xs">{target ? `Writes ${target}` : fallback}</span>
  );
}

function PlacementSection({
  item,
  elevation,
  mapping,
}: {
  item: ElevationItem;
  elevation: Elevation;
  mapping: RackElevationMapping;
}) {
  const { schema, updateAttributes } = useRackElevationStore();
  const [position, setPosition] = React.useState(
    item.position === null ? "" : String(item.position)
  );
  const [face, setFace] = React.useState<RackFace>(item.face);
  const placement = { position: Number(position), face };
  const check = position === "" ? null : checkPlacement(elevation, item, placement);
  const isDirty = position !== String(item.position ?? "") || face !== item.face;
  const kind = item.node.kind;

  return (
    <Section title={`Placement in ${elevation.label}`}>
      <div className="grid grid-cols-2 gap-2">
        <LabeledInput
          label="Position (U)"
          type="number"
          min={1}
          max={elevation.height}
          value={position}
          disabled={!item.targets.position}
          onChange={(event) => setPosition(event.target.value)}
        />
        <div className="flex flex-col gap-1 text-sm">
          Face
          <Select
            aria-label="Face"
            selectedKey={face}
            isDisabled={!item.targets.face}
            onSelectionChange={(key) => setFace(key as RackFace)}
          >
            <SelectTrigger />
            <SelectList>
              <SelectItem id="front">Front</SelectItem>
              <SelectItem id="rear">Rear</SelectItem>
            </SelectList>
          </Select>
        </div>
      </div>
      <div className="flex flex-col gap-0.5">
        <TargetNote
          target={item.targets.position && `${kind}.${item.targets.position.attribute}`}
          fallback="Position is not mapped to an attribute of this object, so it cannot be edited here."
        />
        <TargetNote
          target={item.targets.face && `${kind}.${item.targets.face.attribute}`}
          fallback="Face is not mapped to an attribute of this object, so it cannot be edited here."
        />
        <span className="text-foreground-muted text-xs">
          Height {item.height}U
          {item.targets.height ? "" : ", read from a related object or a fixed value"}
          {item.fullDepth ? " · full depth" : ""}
        </span>
      </div>
      {check && !check.ok && isDirty && <div className="text-danger text-xs">{check.reason}</div>}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="primary"
          isDisabled={!isDirty || !check?.ok}
          onPress={() => updateAttributes(buildPlacementUpdates(item, placement, mapping, schema))}
        >
          Apply placement
        </Button>
        <Button
          size="sm"
          variant="outline"
          isDisabled={item.position === null || !item.targets.position}
          onPress={() => updateAttributes(buildUnmountUpdates(item))}
        >
          Unmount
        </Button>
      </div>
    </Section>
  );
}

function MountedObjectsSection({
  elevation,
  onOpenNode,
}: {
  elevation: Elevation;
  onOpenNode: (nodeId: string) => void;
}) {
  const items = [...elevation.placed].sort((a, b) => (b.position ?? 0) - (a.position ?? 0));
  return (
    <Section title={`Mounted objects (${items.length})`}>
      <ul className="flex flex-col">
        {items.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              onClick={() => onOpenNode(item.node.id)}
              className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-left text-sm hover:bg-content-strong"
            >
              <span className="size-2.5 shrink-0 rounded-sm" style={{ background: item.color }} />
              <span className="truncate">{item.label}</span>
              <span className="ml-auto shrink-0 text-foreground-muted text-xs tabular-nums">
                U{item.position} · {item.face}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function toDraft(value: AttributeValue): string | boolean {
  if (typeof value === "boolean") return value;
  return value === null ? "" : String(value);
}

function fromDraft(draft: string | boolean, attribute: SchemaAttribute): AttributeValue {
  if (attribute.kind === "Boolean") return Boolean(draft);
  if (draft === "") return null;
  if (attribute.kind === "Number") return Number(draft);
  return String(draft);
}

function AttributesSection({
  node,
  attributes,
}: {
  node: GraphNode;
  attributes: SchemaAttribute[];
}) {
  const { updateAttributes } = useRackElevationStore();
  const [draft, setDraft] = React.useState<Record<string, string | boolean>>(() =>
    Object.fromEntries(attributes.map(({ name }) => [name, toDraft(node.attributes[name] ?? null)]))
  );
  const updates: AttributeUpdate[] = attributes.flatMap((attribute) => {
    const value = fromDraft(draft[attribute.name] ?? "", attribute);
    return value === (node.attributes[attribute.name] ?? null)
      ? []
      : [{ nodeId: node.id, attribute: attribute.name, value }];
  });

  return (
    <Section title="Attributes">
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          updateAttributes(updates);
        }}
      >
        {attributes.map((attribute) => (
          <AttributeInput
            key={attribute.name}
            attribute={attribute}
            value={draft[attribute.name] ?? ""}
            onChange={(value) => setDraft((current) => ({ ...current, [attribute.name]: value }))}
          />
        ))}
        <div>
          <Button type="submit" size="sm" variant="primary" isDisabled={updates.length === 0}>
            Save{" "}
            {updates.length > 0 ? `${updates.length} change${updates.length > 1 ? "s" : ""}` : ""}
          </Button>
        </div>
      </form>
    </Section>
  );
}

function AttributeInput({
  attribute,
  value,
  onChange,
}: {
  attribute: SchemaAttribute;
  value: string | boolean;
  onChange: (value: string | boolean) => void;
}) {
  if (attribute.kind === "Boolean") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
        {attribute.label}
      </label>
    );
  }
  if (attribute.kind === "Dropdown" && attribute.choices) {
    return (
      <div className="flex flex-col gap-1 text-sm">
        {attribute.label}
        <Select
          aria-label={attribute.label}
          selectedKey={String(value) || null}
          onSelectionChange={(key) => onChange(String(key))}
        >
          <SelectTrigger />
          <SelectList>
            {attribute.choices.map((choice) => (
              <SelectItem key={choice} id={choice}>
                {choice}
              </SelectItem>
            ))}
          </SelectList>
        </Select>
      </div>
    );
  }
  return (
    <LabeledInput
      label={attribute.label}
      type={attribute.kind === "Number" ? "number" : "text"}
      value={String(value)}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function RelationshipsSection({
  node,
  onOpenNode,
}: {
  node: GraphNode;
  onOpenNode: (nodeId: string) => void;
}) {
  const { nodes, schema } = useRackElevationStore();
  const relationships = schema[node.kind]?.relationships ?? [];

  return (
    <Section title="Relationships">
      <dl className="flex flex-col gap-2 text-sm">
        {relationships.map((relationship) => {
          const raw = node.relationships[relationship.name];
          const peers = (Array.isArray(raw) ? raw : [raw]).flatMap((peerId) => {
            const peer = peerId ? nodes[peerId] : undefined;
            return peer ? [peer] : [];
          });
          return (
            <div key={relationship.name} className="flex flex-col gap-1">
              <dt className="text-foreground-muted text-xs">
                {relationship.label}
                {relationship.cardinality === "many" ? ` (${peers.length})` : ""}
              </dt>
              <dd className="flex flex-wrap gap-1">
                {peers.length === 0 && <span className="text-foreground-muted">-</span>}
                {peers.map((peer) => (
                  <button
                    key={peer.id}
                    type="button"
                    onClick={() => onOpenNode(peer.id)}
                    className="rounded-md border bg-content-muted px-1.5 py-0.5 text-xs hover:bg-content-strong"
                  >
                    {getDisplayLabel(peer, schema)}
                  </button>
                ))}
              </dd>
            </div>
          );
        })}
      </dl>
    </Section>
  );
}
