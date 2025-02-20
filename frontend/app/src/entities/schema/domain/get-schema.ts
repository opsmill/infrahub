import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { GenericSchema, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { store } from "@/shared/stores";

type GetSchema = (kind?: string | null) =>
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

export const getSchema: GetSchema = (kind) => {
  if (!kind) {
    return {
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    };
  }

  const node = store.get(nodeSchemasAtom).find((schema) => schema.kind === kind);
  if (node) {
    return {
      schema: node,
      isGeneric: false,
      isNode: true,
      isProfile: false,
    };
  }

  const generic = store.get(genericSchemasAtom).find((schema) => schema.kind === kind);
  if (generic) {
    return {
      schema: generic,
      isGeneric: true,
      isNode: false,
      isProfile: false,
    };
  }

  const profile = store.get(profileSchemasAtom).find((schema) => schema.kind === kind);
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
