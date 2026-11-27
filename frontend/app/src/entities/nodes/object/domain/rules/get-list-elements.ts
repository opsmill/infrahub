import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { isNodeReference } from "@/entities/nodes/object/domain/rules/is-node-reference";

function getListElement(
  value: unknown,
  position: number,
  isKnownKind: (kind: string) => boolean
): ListElement {
  if (isNodeReference(value) && isKnownKind(value.__typename)) {
    return { position, type: "Node", value, text: getNodeLabel(value) };
  }

  const text = typeof value === "string" ? value : (JSON.stringify(value) ?? "null");
  if (value === null || value === undefined) return { position, type: "Null", value, text };
  if (Array.isArray(value)) return { position, type: "Array", value, text };
  if (typeof value === "object") return { position, type: "Object", value, text };
  if (typeof value === "number") return { position, type: "Number", value, text };
  if (typeof value === "boolean") return { position, type: "Boolean", value, text };
  return { position, type: "Text", value, text };
}

/** `isKnownKind` keeps a stored payload that only looks like a node from rendering as a link. */
export function getListElements(
  values: unknown[],
  isKnownKind: (kind: string) => boolean
): ListElement[] {
  return values.map((value, index) => getListElement(value, index + 1, isKnownKind));
}
