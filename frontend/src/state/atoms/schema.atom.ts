import { atom } from "jotai";
import { components } from "../../infraops";

export type iNodeSchema = components["schemas"]["APINodeSchema"];
export const schemaState = atom<iNodeSchema[]>([]);

export type iGenericSchema = components["schemas"]["APIGenericSchema"];
export const genericsState = atom<iGenericSchema[]>([]);

export const currentSchemaHashAtom = atom<string | null>(null);
