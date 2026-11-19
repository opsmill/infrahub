import type {
  ItemField,
  ItemSourceMapping,
  ValueSource,
} from "@/entities/rack-elevation/domain/model/mapping";
import type { Schema } from "@/entities/rack-elevation/domain/model/schema";

const ITEM_CANDIDATES: Record<ItemField, string[]> = {
  label: ["name", "hostname"],
  subtitle: ["model", "description"],
  position: ["position", "rack_unit", "rack_slot", "u_position", "unit"],
  height: ["u_height", "height", "size_u", "units", "u_count"],
  face: ["face", "mounted_side", "mount_side", "side", "orientation"],
  fullDepth: ["is_full_depth", "full_depth"],
  color: ["color"],
};

const RACK_CANDIDATES = {
  label: ["name"],
  height: ["u_count", "height", "u_height", "units"],
};

/** Finds the first candidate on the kind, then one relationship away from it. */
export function suggestPath(schema: Schema, kind: string, candidates: string[]): ValueSource {
  const schemaKind = schema[kind];
  if (!schemaKind) return { type: "path", path: [] };

  for (const candidate of candidates) {
    if (schemaKind.attributes.some((attribute) => attribute.name === candidate)) {
      return { type: "path", path: [candidate] };
    }
  }
  for (const relationship of schemaKind.relationships) {
    if (relationship.cardinality !== "one") continue;
    const peer = schema[relationship.peer];
    for (const candidate of candidates) {
      if (peer?.attributes.some((attribute) => attribute.name === candidate)) {
        return { type: "path", path: [relationship.name, candidate] };
      }
    }
  }
  return { type: "path", path: [] };
}

export function suggestRackFields(schema: Schema, kind: string) {
  return {
    label: suggestPath(schema, kind, RACK_CANDIDATES.label),
    height: suggestPath(schema, kind, RACK_CANDIDATES.height),
  };
}

export function suggestItemSource(
  schema: Schema,
  rackKind: string,
  relationshipName: string
): ItemSourceMapping {
  const relationship = schema[rackKind]?.relationships.find(
    (candidate) => candidate.name === relationshipName
  );
  const itemKind = relationship?.peer ?? "";
  const fields = Object.fromEntries(
    Object.entries(ITEM_CANDIDATES).map(([field, candidates]) => [
      field,
      suggestPath(schema, itemKind, candidates),
    ])
  ) as Record<ItemField, ValueSource>;

  return {
    id: `source-${crypto.randomUUID()}`,
    name: relationship?.label ?? relationshipName,
    relationship: relationshipName,
    fields,
    frontValues: "front",
    rearValues: "rear, back",
  };
}
