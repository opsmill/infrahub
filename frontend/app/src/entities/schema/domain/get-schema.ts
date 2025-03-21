import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { SchemaResult, resolveSchema } from "@/entities/schema/utils/resolve-schema";
import { store } from "@/shared/stores";

export const getSchema = (kind?: string | null): SchemaResult => {
  return resolveSchema(kind, {
    nodeSchemas: store.get(nodeSchemasAtom),
    genericSchemas: store.get(genericSchemasAtom),
    profileSchemas: store.get(profileSchemasAtom),
    templateSchemas: store.get(templateSchemasAtom),
  });
};
