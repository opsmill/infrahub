import { GenericSchema, Namespace, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { atom } from "jotai";

export const nodeSchemasAtom = atom<readonly NodeSchema[]>([]);
export const genericSchemasAtom = atom<readonly GenericSchema[]>([]);
export const profileSchemasAtom = atom<readonly ProfileSchema[]>([]);
export const namespacesAtom = atom<readonly Namespace[]>([]);

// Current schema hash for tracking changes
export const currentSchemaHashAtom = atom<string | null>(null);
