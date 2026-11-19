import type {
  Elevation,
  ElevationItem,
  RackFace,
  WriteTarget,
} from "@/entities/rack-elevation/domain/model/elevation";
import type {
  ItemSourceMapping,
  RackElevationMapping,
} from "@/entities/rack-elevation/domain/model/mapping";
import type { GraphNode, NodeStore, Schema } from "@/entities/rack-elevation/domain/model/schema";
import {
  isCssColor,
  parseBoolean,
  parseFace,
  parseNumber,
} from "@/entities/rack-elevation/domain/rules/parse-values";
import {
  getDisplayLabel,
  type ResolvedValue,
  resolveCollection,
  resolveValueSource,
} from "@/entities/rack-elevation/domain/rules/resolve-path";

const DEFAULT_RACK_HEIGHT = 42;
const FALLBACK_COLORS = ["#0ea5e9", "#a855f7", "#14b8a6", "#f43f5e", "#84cc16"];

function toWriteTarget(resolved: ResolvedValue, item: GraphNode): WriteTarget | null {
  return resolved.origin?.nodeId === item.id ? resolved.origin : null;
}

function buildItem(
  node: GraphNode,
  source: ItemSourceMapping,
  sourceIndex: number,
  store: NodeStore,
  schema: Schema,
  issues: string[]
): ElevationItem {
  const resolve = (field: keyof ItemSourceMapping["fields"]) =>
    resolveValueSource(source.fields[field], node, store, schema);

  const label = resolve("label");
  const subtitle = resolve("subtitle");
  const position = resolve("position");
  const height = resolve("height");
  const face = resolve("face");
  const color = resolve("color");
  const displayLabel = label.value === null || label.value === "" ? null : String(label.value);
  const colorValue = color.value === null ? "" : String(color.value);
  const parsedFace = parseFace(face.value, source.frontValues, source.rearValues);
  const itemLabel = displayLabel ?? getDisplayLabel(node, schema);

  if (face.value !== null && !parsedFace) {
    issues.push(`${itemLabel}: face value "${face.value}" is not mapped to front or rear.`);
  }

  return {
    key: `${source.id}:${node.id}`,
    node,
    sourceId: source.id,
    sourceName: source.name,
    label: itemLabel,
    subtitle: subtitle.value === null || subtitle.value === "" ? null : String(subtitle.value),
    position: parseNumber(position.value),
    height: Math.max(1, Math.round(parseNumber(height.value) ?? 1)),
    face: parsedFace ?? "front",
    fullDepth: parseBoolean(resolve("fullDepth").value),
    color: isCssColor(colorValue)
      ? colorValue
      : (FALLBACK_COLORS[sourceIndex % FALLBACK_COLORS.length] ?? "#0ea5e9"),
    targets: {
      position: toWriteTarget(position, node),
      face: toWriteTarget(face, node),
      height: toWriteTarget(height, node),
    },
  };
}

export function occupiesFace(item: ElevationItem, face: RackFace): boolean {
  return item.face === face || item.fullDepth;
}

export function overlaps(a: ElevationItem, b: ElevationItem): boolean {
  if (a.position === null || b.position === null) return false;
  return a.position < b.position + b.height && b.position < a.position + a.height;
}

function findConflicts(items: ElevationItem[]): Set<string> {
  const conflicts = new Set<string>();
  for (const [index, a] of items.entries()) {
    for (const b of items.slice(index + 1)) {
      const sharesFace = (["front", "rear"] as const).some(
        (face) => occupiesFace(a, face) && occupiesFace(b, face)
      );
      if (sharesFace && overlaps(a, b)) {
        conflicts.add(a.key);
        conflicts.add(b.key);
      }
    }
  }
  return conflicts;
}

export function buildElevation(
  mapping: RackElevationMapping,
  rack: GraphNode,
  store: NodeStore,
  schema: Schema
): Elevation {
  const issues: string[] = [];
  const label = resolveValueSource(mapping.rack.label, rack, store, schema).value;
  const parsedHeight = parseNumber(
    resolveValueSource(mapping.rack.height, rack, store, schema).value
  );
  const height = parsedHeight && parsedHeight > 0 ? Math.round(parsedHeight) : DEFAULT_RACK_HEIGHT;
  if (!parsedHeight) {
    issues.push(`The rack height cannot be read, so the view uses ${DEFAULT_RACK_HEIGHT}U.`);
  }

  const items = mapping.itemSources.flatMap((source, sourceIndex) =>
    resolveCollection(source.relationship, rack, store).map((node) =>
      buildItem(node, source, sourceIndex, store, schema, issues)
    )
  );

  const placed: ElevationItem[] = [];
  const unplaced: ElevationItem[] = [];
  for (const item of items) {
    if (item.position === null) {
      unplaced.push(item);
    } else if (item.position < 1 || item.position + item.height - 1 > height) {
      issues.push(`${item.label}: U${item.position} (${item.height}U) is outside the rack.`);
      unplaced.push(item);
    } else {
      placed.push(item);
    }
  }

  const conflicts = findConflicts(placed);
  for (const key of conflicts) {
    const item = placed.find((candidate) => candidate.key === key);
    if (item) issues.push(`${item.label}: overlaps another object at U${item.position}.`);
  }

  return {
    rack,
    label: label === null || label === "" ? getDisplayLabel(rack, schema) : String(label),
    height,
    placed,
    unplaced,
    conflicts,
    issues,
  };
}
