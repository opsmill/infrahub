import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export type ListElementType = "Node" | "Object" | "Array" | "Text" | "Number" | "Boolean" | "Null";

interface ListElementBase {
  position: number;
  text: string;
}

/** One element of a List value, or of an Any value holding an array. */
export type ListElement =
  | (ListElementBase & { type: "Node"; value: NodeCore })
  | (ListElementBase & { type: Exclude<ListElementType, "Node">; value: unknown });
