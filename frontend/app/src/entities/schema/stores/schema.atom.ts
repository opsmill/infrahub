import { atom } from "jotai";

import type {
  GenericSchema,
  Namespace,
  NodeSchema,
  ProfileSchema,
  TemplateSchema,
} from "@/entities/schema/types";

export const nodeSchemasAtom = atom<NodeSchema[]>([]);
export const genericSchemasAtom = atom<GenericSchema[]>([]);
export const profileSchemasAtom = atom<ProfileSchema[]>([]);
export const templateSchemasAtom = atom<TemplateSchema[]>([]);
export const namespacesAtom = atom<Namespace[]>([]);
