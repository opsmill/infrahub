import { atom } from "jotai";
import { components } from "../../infraops";

export type iNodeSchema = components["schemas"]["NodeSchema"];
export const schemaState = atom<iNodeSchema[]>([]);

export type iGenericSchema = components["schemas"]["GenericSchema"];
export const genericsState = atom<iGenericSchema[]>([]);

export const currentSchemaHashAtom = atom<string | null>(null);
