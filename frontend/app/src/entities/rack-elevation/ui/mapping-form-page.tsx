import { Button, LinkButton, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";
import { PlusIcon, Trash2Icon } from "lucide-react";
import React from "react";
import { useNavigate } from "react-router";

import {
  ITEM_FIELDS,
  type ItemField,
  type ItemSourceMapping,
  type RackElevationMapping,
} from "@/entities/rack-elevation/domain/model/mapping";
import type { GraphNode, Schema } from "@/entities/rack-elevation/domain/model/schema";
import { buildElevation } from "@/entities/rack-elevation/domain/rules/build-elevation";
import { buildGraphqlQuery } from "@/entities/rack-elevation/domain/rules/build-graphql-query";
import {
  getDisplayLabel,
  resolveCollection,
  resolveValueSource,
} from "@/entities/rack-elevation/domain/rules/resolve-path";
import {
  suggestItemSource,
  suggestRackFields,
} from "@/entities/rack-elevation/domain/rules/suggest-mapping";
import { LabeledInput } from "@/entities/rack-elevation/ui/labeled-input";
import { Section } from "@/entities/rack-elevation/ui/object-details";
import { RackElevation2D } from "@/entities/rack-elevation/ui/rack-elevation-2d";
import { useRackElevationStore } from "@/entities/rack-elevation/ui/rack-elevation-store";
import { ValueSourceField } from "@/entities/rack-elevation/ui/value-source-field";

const PREVIEW_UNIT_HEIGHT = 11;

function createMapping(schema: Schema, rackKind: string): RackElevationMapping {
  return {
    id: `mapping-${crypto.randomUUID()}`,
    name: "",
    rackKind,
    rack: suggestRackFields(schema, rackKind),
    itemSources: [],
  };
}

export function MappingFormPage({ mappingId }: { mappingId?: string }) {
  const { mappings, nodes, schema, saveMapping, deleteMapping } = useRackElevationStore();
  const navigate = useNavigate();
  const existing = mappings.find((candidate) => candidate.id === mappingId);
  const [draft, setDraft] = React.useState<RackElevationMapping>(
    () => existing ?? createMapping(schema, "DcimRack")
  );
  const [sampleRackId, setSampleRackId] = React.useState<string | null>(null);

  const kinds = Object.values(schema).sort((a, b) => a.label.localeCompare(b.label));
  const racks = Object.values(nodes).filter((node) => node.kind === draft.rackKind);
  const sampleRack = racks.find((node) => node.id === sampleRackId) ?? racks[0];
  const rackSchema = schema[draft.rackKind];
  const collections =
    rackSchema?.relationships.filter((relationship) => relationship.cardinality === "many") ?? [];
  const unusedCollections = collections.filter(
    (relationship) => !draft.itemSources.some((source) => source.relationship === relationship.name)
  );
  const elevation = sampleRack ? buildElevation(draft, sampleRack, nodes, schema) : null;
  const canSave = draft.name.trim() !== "" && !!rackSchema;

  const updateSource = (sourceId: string, update: Partial<ItemSourceMapping>) =>
    setDraft((current) => ({
      ...current,
      itemSources: current.itemSources.map((source) =>
        source.id === sourceId ? { ...source, ...update } : source
      ),
    }));

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b p-4">
        <div>
          <h1 className="font-semibold text-lg">
            {existing ? `Edit mapping: ${existing.name}` : "New rack elevation mapping"}
          </h1>
          <p className="text-foreground-muted text-xs">
            Link each value of the rack view to an attribute or relationship of your schema.
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          {existing && (
            <Button
              size="sm"
              variant="danger-outline"
              onPress={() => {
                deleteMapping(existing.id);
                navigate("/rack-elevation");
              }}
            >
              <Trash2Icon />
              Delete
            </Button>
          )}
          <LinkButton size="sm" variant="outline" href="/rack-elevation">
            Cancel
          </LinkButton>
          <Button
            size="sm"
            variant="primary"
            isDisabled={!canSave}
            onPress={() => {
              saveMapping(draft);
              navigate(`/rack-elevation?mapping=${draft.id}`);
            }}
          >
            Save mapping
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-auto p-4">
          <Section title="Rack">
            <LabeledInput
              label="Mapping name"
              value={draft.name}
              placeholder="Data center racks"
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
            <div className="flex flex-col gap-1 text-sm">
              Rack kind
              <Select
                aria-label="Rack kind"
                selectedKey={draft.rackKind}
                onSelectionChange={(key) => {
                  const next = createMapping(schema, String(key));
                  setDraft({ ...next, id: draft.id, name: draft.name });
                  setSampleRackId(null);
                }}
              >
                <SelectTrigger />
                <SelectList items={kinds.map((kind) => ({ id: kind.kind, label: kind.label }))}>
                  {(item) => (
                    <SelectItem id={item.id} textValue={item.label}>
                      {item.label} <span className="text-foreground-muted">{item.id}</span>
                    </SelectItem>
                  )}
                </SelectList>
              </Select>
              <span className="text-foreground-muted text-xs">
                Any kind of the schema can be a rack. The view reads the values below from objects
                of this kind.
              </span>
            </div>
            <div>
              <ValueSourceField
                label="Rack label"
                description="Name shown above the rack"
                kind={draft.rackKind}
                schema={schema}
                value={draft.rack.label}
                sample={
                  sampleRack &&
                  resolveValueSource(draft.rack.label, sampleRack, nodes, schema).value
                }
                onChange={(label) => setDraft({ ...draft, rack: { ...draft.rack, label } })}
              />
              <ValueSourceField
                label="Height (U)"
                description="Number of units in the rack"
                kind={draft.rackKind}
                schema={schema}
                value={draft.rack.height}
                sample={
                  sampleRack &&
                  resolveValueSource(draft.rack.height, sampleRack, nodes, schema).value
                }
                onChange={(height) => setDraft({ ...draft, rack: { ...draft.rack, height } })}
              />
            </div>
          </Section>

          {draft.itemSources.map((source) => (
            <ItemSourceEditor
              key={source.id}
              source={source}
              rackKind={draft.rackKind}
              schema={schema}
              sampleItem={
                sampleRack
                  ? resolveCollection(source.relationship, sampleRack, nodes)[0]
                  : undefined
              }
              onChange={(update) => updateSource(source.id, update)}
              onRemove={() =>
                setDraft({
                  ...draft,
                  itemSources: draft.itemSources.filter((candidate) => candidate.id !== source.id),
                })
              }
            />
          ))}

          <Section title="Mounted objects">
            <p className="text-foreground-muted text-xs">
              Select a relationship of the rack that lists the objects to draw in it. Add one group
              per relationship, for example devices, patch panels and power distribution units.
            </p>
            {unusedCollections.length === 0 ? (
              <p className="text-foreground-muted text-xs">
                Every relationship of this kind that can hold several objects is already added.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {unusedCollections.map((relationship) => (
                  <Button
                    key={relationship.name}
                    size="sm"
                    variant="outline"
                    onPress={() =>
                      setDraft({
                        ...draft,
                        itemSources: [
                          ...draft.itemSources,
                          suggestItemSource(schema, draft.rackKind, relationship.name),
                        ],
                      })
                    }
                  >
                    <PlusIcon />
                    {relationship.label}
                    <span className="text-foreground-muted">{relationship.peer}</span>
                  </Button>
                ))}
              </div>
            )}
          </Section>
        </div>

        <aside className="flex w-136 shrink-0 flex-col gap-3 overflow-auto border-l p-3">
          <Section title="Preview">
            <Select
              aria-label="Sample rack"
              selectedKey={sampleRack?.id ?? null}
              onSelectionChange={(key) => setSampleRackId(String(key))}
            >
              <SelectTrigger size="sm" />
              <SelectList items={racks}>
                {(item: GraphNode) => (
                  <SelectItem id={item.id}>{getDisplayLabel(item, schema)}</SelectItem>
                )}
              </SelectList>
            </Select>
            {elevation ? (
              <>
                <RackElevation2D elevation={elevation} unitHeight={PREVIEW_UNIT_HEIGHT} />
                <p className="text-foreground-muted text-xs">
                  {elevation.placed.length} mounted, {elevation.unplaced.length} not mounted,{" "}
                  {elevation.issues.length} issues
                </p>
              </>
            ) : (
              <p className="text-foreground-muted text-xs">
                No objects of kind {draft.rackKind} exist to preview.
              </p>
            )}
          </Section>
          <Section title="Generated GraphQL query">
            <p className="text-foreground-muted text-xs">
              The query Infrahub would run to load one rack with this mapping.
            </p>
            <pre className="overflow-auto rounded-lg bg-content-muted p-2 font-mono text-xxs">
              {buildGraphqlQuery(draft, schema)}
            </pre>
          </Section>
        </aside>
      </div>
    </div>
  );
}

function ItemSourceEditor({
  source,
  rackKind,
  schema,
  sampleItem,
  onChange,
  onRemove,
}: {
  source: ItemSourceMapping;
  rackKind: string;
  schema: Schema;
  sampleItem: GraphNode | undefined;
  onChange: (update: Partial<ItemSourceMapping>) => void;
  onRemove: () => void;
}) {
  const { nodes } = useRackElevationStore();
  const relationship = schema[rackKind]?.relationships.find(
    (candidate) => candidate.name === source.relationship
  );
  const itemKind = relationship?.peer ?? "";
  const setField = (field: ItemField, value: ItemSourceMapping["fields"][ItemField]) =>
    onChange({ fields: { ...source.fields, [field]: value } });

  return (
    <Section title={`Mounted objects: ${relationship?.label ?? source.relationship}`}>
      <div className="flex flex-wrap items-end gap-2">
        <LabeledInput
          label="Group name"
          labelClassName="flex-1"
          value={source.name}
          onChange={(event) => onChange({ name: event.target.value })}
        />
        <div className="flex flex-col gap-1 text-sm">
          Read from
          <code className="flex h-10 items-center rounded-xl border bg-content-muted px-2 text-xs">
            {rackKind}.{source.relationship} → {itemKind}
          </code>
        </div>
        <Button
          size="md"
          variant="ghost"
          shape="square"
          aria-label="Remove group"
          onPress={onRemove}
        >
          <Trash2Icon />
        </Button>
      </div>
      <div>
        {ITEM_FIELDS.map(({ field, label, description }) => (
          <React.Fragment key={field}>
            <ValueSourceField
              label={label}
              description={description}
              kind={itemKind}
              schema={schema}
              value={source.fields[field]}
              sample={
                sampleItem &&
                resolveValueSource(source.fields[field], sampleItem, nodes, schema).value
              }
              onChange={(value) => setField(field, value)}
            />
            {field === "face" && (
              <div className="grid grid-cols-2 gap-2 border-b pb-3">
                <LabeledInput
                  label="Values that mean front (comma separated)"
                  labelClassName="text-xs"
                  value={source.frontValues}
                  onChange={(event) => onChange({ frontValues: event.target.value })}
                />
                <LabeledInput
                  label="Values that mean rear (comma separated)"
                  labelClassName="text-xs"
                  value={source.rearValues}
                  onChange={(event) => onChange({ rearValues: event.target.value })}
                />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </Section>
  );
}
