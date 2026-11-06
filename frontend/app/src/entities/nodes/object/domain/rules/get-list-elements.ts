import type {
  ListElement,
  ListElementType,
} from "@/entities/nodes/object/domain/model/list-element";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { isNodeReference } from "@/entities/nodes/object/domain/rules/is-node-reference";

function getListElementType(value: unknown): ListElementType {
  if (value === null || value === undefined) return "Null";
  if (isNodeReference(value)) return "Node";
  if (Array.isArray(value)) return "Array";
  if (typeof value === "object") return "Object";
  if (typeof value === "number") return "Number";
  if (typeof value === "boolean") return "Boolean";
  return "Text";
}

function getListElementText(value: unknown): string {
  if (isNodeReference(value)) return getNodeLabel(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value) ?? "null";
}

export function getListElements(values: unknown[]): ListElement[] {
  return values.map((value, index) => ({
    position: index + 1,
    value,
    type: getListElementType(value),
    text: getListElementText(value),
  }));
}
