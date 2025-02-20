import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { GenericSchema, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { useAtomValue } from "jotai/index";

type UseSchema = (kind: string | null | undefined) =>
  | {
      schema: NodeSchema;
      isGeneric: false;
      isNode: true;
      isProfile: false;
    }
  | {
      schema: GenericSchema;
      isGeneric: true;
      isNode: false;
      isProfile: false;
    }
  | {
      schema: ProfileSchema;
      isGeneric: false;
      isNode: false;
      isProfile: true;
    }
  | {
      schema: null;
      isGeneric: false;
      isNode: false;
      isProfile: false;
    };

export const useSchema: UseSchema = (kind) => {
  const nodesSchema = useAtomValue(nodeSchemasAtom);
  const profilesSchema = useAtomValue(profileSchemasAtom);
  const genericsSchema = useAtomValue(genericSchemasAtom);

  if (!kind) {
    return {
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    };
  }

  const node = nodesSchema.find((schema) => schema.kind === kind);
  if (node) {
    return {
      schema: node,
      isGeneric: false,
      isNode: true,
      isProfile: false,
    };
  }

  const generic = genericsSchema.find((schema) => schema.kind === kind);
  if (generic) {
    return {
      schema: generic,
      isGeneric: true,
      isNode: false,
      isProfile: false,
    };
  }

  const profile = profilesSchema.find((schema) => schema.kind === kind);
  if (profile) {
    return {
      schema: profile,
      isGeneric: false,
      isNode: false,
      isProfile: true,
    };
  }

  return {
    schema: null,
    isGeneric: false,
    isNode: false,
    isProfile: false,
  };
};
