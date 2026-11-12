import type {
  RackElevationItem,
  RackElevationRack,
} from "@/entities/rack-elevation/domain/model/rack-elevation";

const CSV_HEADER = ["rack", "unit", "face", "label", "type", "height", "placement"];
const FORMULA_PREFIXES = ["=", "+", "-", "@"];

const escapeCsvField = (value: string) => {
  const safeValue = FORMULA_PREFIXES.some((prefix) => value.startsWith(prefix))
    ? `'${value}`
    : value;

  return /[",\n\r]/.test(safeValue) ? `"${safeValue.replaceAll('"', '""')}"` : safeValue;
};

const toCsvLine = (fields: string[]) => fields.map(escapeCsvField).join(",");

/** One header line, then one line per item. */
export const toCsv = (rack: RackElevationRack, items: RackElevationItem[]) => {
  const lines = items.map((item) =>
    toCsvLine([
      rack.display_label,
      item.position === null ? "" : String(item.position),
      item.face?.toLowerCase() ?? "",
      item.label,
      item.type_display_label ?? "",
      String(item.u_height),
      item.placement.toLowerCase(),
    ])
  );

  return [toCsvLine(CSV_HEADER), ...lines].join("\n");
};
