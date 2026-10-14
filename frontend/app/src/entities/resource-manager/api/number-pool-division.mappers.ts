import type {
  NumberPoolDivisionEntryNode,
  NumberPoolDivisionNode,
  NumberPoolDivisionsNode,
} from "@/entities/resource-manager/api/get-number-pool-divisions-from-api";
import { mapToNumberPoolUsage } from "@/entities/resource-manager/api/number-pool-utilization.mappers";
import type {
  NumberPoolDivision,
  NumberPoolDivisionEntry,
  NumberPoolDivisions,
  NumberPoolDivisionValue,
} from "@/entities/resource-manager/domain/model/number-pool";

const toDivisionValue = (value: unknown): NumberPoolDivisionValue => {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  return String(value ?? "");
};

const mapToNumberPoolDivisionEntry = (
  entry: NumberPoolDivisionEntryNode
): NumberPoolDivisionEntry => ({
  path: entry.path,
  value: toDivisionValue(entry.value),
  label: entry.display_label,
  peerKind: entry.peer_kind ?? null,
});

const mapToNumberPoolDivision = (division: NumberPoolDivisionNode): NumberPoolDivision => ({
  label: division.display_label,
  entries: division.entries.map(mapToNumberPoolDivisionEntry),
  usage: mapToNumberPoolUsage(division.figures),
});

export const mapToNumberPoolDivisions = (node: NumberPoolDivisionsNode): NumberPoolDivisions => ({
  fields: node.allocation_scope.map((element) => element.name),
  divisions: node.divisions.map(mapToNumberPoolDivision),
});
