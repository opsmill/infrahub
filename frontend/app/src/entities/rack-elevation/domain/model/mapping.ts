export type ValueSource =
  | { type: "path"; path: string[] }
  | { type: "template"; template: string }
  | { type: "constant"; value: string };

export type ValueSourceType = ValueSource["type"];

export type ItemField =
  | "label"
  | "subtitle"
  | "position"
  | "height"
  | "face"
  | "fullDepth"
  | "color";

export interface ItemSourceMapping {
  id: string;
  name: string;
  relationship: string;
  fields: Record<ItemField, ValueSource>;
  frontValues: string;
  rearValues: string;
}

export interface RackElevationMapping {
  id: string;
  name: string;
  rackKind: string;
  rack: {
    label: ValueSource;
    height: ValueSource;
  };
  itemSources: ItemSourceMapping[];
}

export const EMPTY_PATH: ValueSource = { type: "path", path: [] };

export const ITEM_FIELDS: { field: ItemField; label: string; description: string }[] = [
  { field: "label", label: "Label", description: "Text shown on the object in the rack" },
  { field: "subtitle", label: "Subtitle", description: "Secondary text, such as the model" },
  { field: "position", label: "Position (U)", description: "Lowest unit the object occupies" },
  { field: "height", label: "Height (U)", description: "Number of units the object occupies" },
  { field: "face", label: "Face", description: "Side of the rack the object mounts on" },
  {
    field: "fullDepth",
    label: "Full depth",
    description: "When true, the object also blocks the opposite face",
  },
  { field: "color", label: "Color", description: "CSS color, such as a role color" },
];
