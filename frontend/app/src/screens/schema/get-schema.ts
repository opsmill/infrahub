import {
  IProfileSchema,
  genericsState,
  iGenericSchema,
  iNodeSchema,
  profilesAtom,
  schemaState,
} from "@/screens/schema/schema.atom";
import { store } from "@/shared/stores";

type GetSchema = (kind?: string | null) =>
  | {
      schema: iNodeSchema;
      isGeneric: false;
      isNode: true;
      isProfile: false;
    }
  | {
      schema: iGenericSchema;
      isGeneric: true;
      isNode: false;
      isProfile: false;
    }
  | {
      schema: IProfileSchema;
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

  const node = store.get(schemaState).find((schema) => schema.kind === kind);
  if (node) {
    return {
      schema: node,
      isGeneric: false,
      isNode: true,
      isProfile: false,
    };
  }

  const generic = store.get(genericsState).find((schema) => schema.kind === kind);
  if (generic) {
    return {
      schema: generic,
      isGeneric: true,
      isNode: false,
      isProfile: false,
    };
  }

  const profile = store.get(profilesAtom).find((schema) => schema.kind === kind);
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
