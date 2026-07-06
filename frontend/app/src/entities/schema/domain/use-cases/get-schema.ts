import { store } from "@/shared/stores";

import { resolveSchema, type SchemaResult } from "@/entities/schema/domain/rules/resolve-schema";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

export const getSchema = (kind?: string | null): SchemaResult => {
  return resolveSchema(kind, {
    nodeSchemas: store.get(nodeSchemasAtom),
    genericSchemas: store.get(genericSchemasAtom),
    profileSchemas: store.get(profileSchemasAtom),
    templateSchemas: store.get(templateSchemasAtom),
  });
};
