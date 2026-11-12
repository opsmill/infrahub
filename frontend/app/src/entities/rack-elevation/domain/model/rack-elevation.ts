import {
  type RackElevationItem as GeneratedRackElevationItem,
  type RackElevationKind as GeneratedRackElevationKind,
  type RackElevationRack as GeneratedRackElevationRack,
  RackElevationRole as GeneratedRackElevationRole,
  RackFace as GeneratedRackFace,
  RackItemPlacement as GeneratedRackItemPlacement,
} from "@/shared/api/graphql/generated/types";

export const RACK_ELEVATION_TAB = "elevation";

export const RACK_LABEL_BY_QSP = "label_by";
export const RACK_COLOR_BY_QSP = "color_by";

export const RackElevationRole = GeneratedRackElevationRole;
export type RackElevationRole = GeneratedRackElevationRole;

export const RackFace = GeneratedRackFace;
export type RackFace = GeneratedRackFace;

export const RackItemPlacement = GeneratedRackItemPlacement;
export type RackItemPlacement = GeneratedRackItemPlacement;

export const RACK_FACES = [RackFace.FRONT, RackFace.REAR] as const;

export type RackElevationKind = Omit<GeneratedRackElevationKind, "__typename">;
export type RackElevationRack = Omit<GeneratedRackElevationRack, "__typename">;
export type RackElevationItem = Omit<GeneratedRackElevationItem, "__typename">;

export type RackElevation = {
  rack: RackElevationRack;
  items: RackElevationItem[];
};

export type RackItemAttributeOption = {
  name: string;
  label: string;
};

export type RackItemAttributeOptions = {
  labelBy: RackItemAttributeOption[];
  colorBy: RackItemAttributeOption[];
};

export type UnitRange = {
  start: number;
  end: number;
};

export type FreeUnitsByFace = Record<RackFace, UnitRange[]>;
export type PlacementTargetsByFace = Record<RackFace, Set<number>>;
