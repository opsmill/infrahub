import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { SchemaResult, resolveSchema } from "@/entities/schema/utils/resolve-schema";
import { useAtomValue } from "jotai/index";

export const useSchema = (kind: string | null | undefined): SchemaResult => {
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const profileSchemas = useAtomValue(profileSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);

  return resolveSchema(kind, {
    nodeSchemas,
    genericSchemas,
    profileSchemas,
  });
};
