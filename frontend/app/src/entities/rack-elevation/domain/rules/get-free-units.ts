import {
  type FreeUnitsByFace,
  type PlacementTargetsByFace,
  RACK_FACES,
  type RackElevationItem,
  type RackFace,
  RackItemPlacement,
  type UnitRange,
} from "@/entities/rack-elevation/domain/model/rack-elevation";

type MountedItem = RackElevationItem & { position: number; face: RackFace };

const isMountedItem = (item: RackElevationItem): item is MountedItem =>
  item.placement === RackItemPlacement.MOUNTED &&
  item.position !== null &&
  item.face !== null &&
  item.u_height > 0;

const getFacesUsedBy = (item: RackElevationItem, face: RackFace): readonly RackFace[] =>
  item.full_depth ? RACK_FACES : [face];

const getOccupiedUnits = (items: RackElevationItem[], ignoredItemId?: string) => {
  const occupied: Record<RackFace, Set<number>> = {
    FRONT: new Set(),
    REAR: new Set(),
  };

  for (const item of items) {
    if (!isMountedItem(item) || item.id === ignoredItemId) continue;

    for (const face of getFacesUsedBy(item, item.face)) {
      for (let unit = item.position; unit < item.position + item.u_height; unit++) {
        occupied[face].add(unit);
      }
    }
  }

  return occupied;
};

export interface GetFreeUnitsParams {
  items: RackElevationItem[];
  uHeight: number;
}

export const getFreeUnits = ({ items, uHeight }: GetFreeUnitsParams): FreeUnitsByFace => {
  const occupied = getOccupiedUnits(items);

  const rangesOf = (face: RackFace) => {
    const ranges: UnitRange[] = [];
    let current: UnitRange | null = null;

    for (let unit = 1; unit <= uHeight; unit++) {
      if (occupied[face].has(unit)) {
        current = null;
      } else if (current) {
        current.end = unit;
      } else {
        current = { start: unit, end: unit };
        ranges.push(current);
      }
    }

    return ranges;
  };

  return { FRONT: rangesOf("FRONT"), REAR: rangesOf("REAR") };
};

export interface GetPlacementTargetsParams extends GetFreeUnitsParams {
  movingItem: RackElevationItem;
}

/**
 * Units where the moving item would fit, ignoring the units it uses now. Only a hint: the backend
 * checks every placement.
 */
export const getPlacementTargets = ({
  items,
  uHeight,
  movingItem,
}: GetPlacementTargetsParams): PlacementTargetsByFace => {
  const targets: PlacementTargetsByFace = { FRONT: new Set(), REAR: new Set() };
  if (movingItem.u_height <= 0) return targets;

  const occupied = getOccupiedUnits(items, movingItem.id);

  for (const face of RACK_FACES) {
    const requiredFaces = getFacesUsedBy(movingItem, face);

    for (let start = 1; start + movingItem.u_height - 1 <= uHeight; start++) {
      const fits = requiredFaces.every((requiredFace) =>
        Array.from({ length: movingItem.u_height }, (_, offset) => start + offset).every(
          (unit) => !occupied[requiredFace].has(unit)
        )
      );
      if (fits) targets[face].add(start);
    }
  }

  return targets;
};
