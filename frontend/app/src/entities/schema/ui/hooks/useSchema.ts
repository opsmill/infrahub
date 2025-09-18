import { useAtomValue } from "jotai/index";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { resolveSchema, type SchemaResult } from "@/entities/schema/utils/resolve-schema";

export const useSchema = (kind: string | null | undefined): SchemaResult => {
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const profileSchemas = useAtomValue(profileSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);
  const templateSchemas = useAtomValue(templateSchemasAtom);

  return resolveSchema(kind, {
    nodeSchemas,
    genericSchemas,
    profileSchemas,
    templateSchemas,
  });
};
