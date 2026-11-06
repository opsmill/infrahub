import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";

/** Matches the text the user reads, and the kind of a node, never the serialized node object. */
export function filterListElements(elements: ListElement[], query: string): ListElement[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return elements;

  return elements.filter((element) => {
    const kind = element.type === "Node" ? element.value.__typename : "";
    return `${element.text} ${kind}`.toLowerCase().includes(needle);
  });
}
