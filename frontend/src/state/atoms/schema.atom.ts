import { atom } from "jotai";
import { components } from "../../infraops";

export type iNodeSchema = components["schemas"]["APINodeSchema"];
export const schemaState = atom<iNodeSchema[]>([]);

export type iGenericSchema = components["schemas"]["APIGenericSchema"];
export const genericsState = atom<iGenericSchema[]>([]);

export type iNamespace = {
  name: string;
  user_editable: boolean;
};
export const namespacesState = atom<iNamespace[]>([]);

export interface iGenericSchemaMapping {
  [node: string]: string[];
}
export const genericSchemaState = atom<iGenericSchemaMapping>({});

export type iRelationshipSchema = components["schemas"]["RelationshipSchema"];
export const currentSchemaHashAtom = atom<string | null>(null);
