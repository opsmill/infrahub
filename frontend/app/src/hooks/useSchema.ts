import {
  IProfileSchema,
  genericsState,
  iGenericSchema,
  iNodeSchema,
  profilesAtom,
  schemaState,
} from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";

type UseSchema = (kind?: string | null) =>
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

export const useSchema: UseSchema = (kind) => {
  const nodesSchema = useAtomValue(schemaState);
  const profilesSchema = useAtomValue(profilesAtom);
  const genericsSchema = useAtomValue(genericsState);

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
