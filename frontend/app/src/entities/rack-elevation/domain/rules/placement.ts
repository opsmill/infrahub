import type {
  Elevation,
  ElevationItem,
  RackFace,
} from "@/entities/rack-elevation/domain/model/elevation";
import type { RackElevationMapping } from "@/entities/rack-elevation/domain/model/mapping";
import type { AttributeUpdate, Schema } from "@/entities/rack-elevation/domain/model/schema";
import { occupiesFace } from "@/entities/rack-elevation/domain/rules/build-elevation";
import { formatFace, formatNumberLike } from "@/entities/rack-elevation/domain/rules/parse-values";

export interface Placement {
  position: number;
  face: RackFace;
}

export type PlacementCheck = { ok: true } | { ok: false; reason: string };

export function canMove(item: ElevationItem, face: RackFace): boolean {
  if (!item.targets.position) return false;
  return face === item.face || item.targets.face !== null;
}

export function checkPlacement(
  elevation: Elevation,
  item: ElevationItem,
  { position, face }: Placement
): PlacementCheck {
  if (!item.targets.position) {
    return { ok: false, reason: "The position is not mapped to an attribute of this object." };
  }
  if (face !== item.face && !item.targets.face) {
    return { ok: false, reason: "The face is not mapped to an attribute of this object." };
  }
  if (position < 1 || position + item.height - 1 > elevation.height) {
    return {
      ok: false,
      reason: `U${position} to U${position + item.height - 1} is outside the rack.`,
    };
  }

  const moved: ElevationItem = { ...item, position, face };
  const blocker = elevation.placed.find(
    (other) =>
      other.key !== item.key &&
      other.position !== null &&
      other.position < position + item.height &&
      position < other.position + other.height &&
      (["front", "rear"] as const).some((f) => occupiesFace(moved, f) && occupiesFace(other, f))
  );
  if (blocker) return { ok: false, reason: `${blocker.label} already uses U${blocker.position}.` };

  return { ok: true };
}

export function buildPlacementUpdates(
  item: ElevationItem,
  { position, face }: Placement,
  mapping: RackElevationMapping,
  schema: Schema
): AttributeUpdate[] {
  const updates: AttributeUpdate[] = [];
  const source = mapping.itemSources.find((candidate) => candidate.id === item.sourceId);
  const positionTarget = item.targets.position;
  const faceTarget = item.targets.face;

  if (positionTarget && position !== item.position) {
    const previous = item.node.attributes[positionTarget.attribute] ?? null;
    updates.push({ ...positionTarget, value: formatNumberLike(previous, position) });
  }
  if (faceTarget && source && face !== item.face) {
    const previous = item.node.attributes[faceTarget.attribute] ?? null;
    const attribute = schema[item.node.kind]?.attributes.find(
      (candidate) => candidate.name === faceTarget.attribute
    );
    updates.push({
      ...faceTarget,
      value: formatFace(face, previous, source.frontValues, source.rearValues, attribute),
    });
  }
  return updates;
}

export function buildUnmountUpdates(item: ElevationItem): AttributeUpdate[] {
  return item.targets.position ? [{ ...item.targets.position, value: null }] : [];
}
