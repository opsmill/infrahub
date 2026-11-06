export type ListElementType = "Node" | "Object" | "Array" | "Text" | "Number" | "Boolean" | "Null";

/** One element of a List value, or of an Any value holding an array. */
export interface ListElement {
  position: number;
  value: unknown;
  type: ListElementType;
  text: string;
}
