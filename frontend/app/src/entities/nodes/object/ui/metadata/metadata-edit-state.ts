import { atom } from "jotai";

export const fieldMetadataEditState = atom<{
  type: "attribute" | "relationship";
  attributeOrRelationshipName: any;
  label: string;
} | null>(null);
