import { atom } from "jotai";

export const metaEditFieldDetailsState = atom<{
  type: "attribute" | "relationship";
  attributeOrRelationshipName: any;
  label: string;
} | null>(null);
