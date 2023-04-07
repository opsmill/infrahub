import { atom } from "jotai";
import { components } from "../../infraops";
export type iNodeSchema = components["schemas"]["NodeSchema"];

export const schemaState = atom<iNodeSchema[]>([]);

export interface iGenericSchemaMapping {
    [node: string]: string[];
}
export const genericSchemaState = atom<iGenericSchemaMapping>({});