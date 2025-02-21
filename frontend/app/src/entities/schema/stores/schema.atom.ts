import { GenericSchema, Namespace, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { atom } from "jotai";

export const nodeSchemasAtom = atom<NodeSchema[]>([]);
export const genericSchemasAtom = atom<GenericSchema[]>([]);
export const profileSchemasAtom = atom<ProfileSchema[]>([]);
export const namespacesAtom = atom<Namespace[]>([]);

// Current schema hash for tracking changes
export const currentSchemaHashAtom = atom<string | null>(null);
