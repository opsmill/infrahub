import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { GenericSchema, ModelSchema, NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { store } from "@/shared/stores";

export const isOfKind = (kind: string, schema: ModelSchema) => {
  if (schema.kind === kind) return true;
  if (!isGenericSchema(schema) && schema.inherit_from?.includes(kind)) return true;
  return false;
};

export const isGenericSchema = (schema: ModelSchema): schema is GenericSchema => {
  return "used_by" in schema;
};

export const isNodeSchema = (schema: ModelSchema): schema is NodeSchema => {
  return "inherit_from" in schema;
};

export const isProfileSchema = (schema: ModelSchema): schema is ProfileSchema => {
  return schema.namespace === "Profile";
};

export const isHierarchicalSchema = (
  schema: ModelSchema
): schema is ModelSchema & { hierarchy: string } => {
  return "hierarchy" in schema && !!schema.hierarchy;
};

export const getRootSchemaOfHierarchicalSchema = (schema: NodeSchema): NodeSchema => {
  const nodes = store.get(nodeSchemasAtom);
  const parentSchema = nodes.find(({ kind }) => kind === schema.parent);

  if (!parentSchema) return schema;
  return getRootSchemaOfHierarchicalSchema(parentSchema);
};

export type SchemaResult =
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

export function resolveSchema(
  kind: string | null | undefined,
  schemas: {
    nodes: NodeSchema[];
    generics: GenericSchema[];
    profiles: ProfileSchema[];
  }
): SchemaResult {
  if (!kind) {
    return {
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
    };
  }

  const node = schemas.nodes.find((schema) => schema.kind === kind);
  if (node) {
    return {
      schema: node,
      isGeneric: false,
      isNode: true,
      isProfile: false,
    };
  }

  const generic = schemas.generics.find((schema) => schema.kind === kind);
  if (generic) {
    return {
      schema: generic,
      isGeneric: true,
      isNode: false,
      isProfile: false,
    };
  }

  const profile = schemas.profiles.find((schema) => schema.kind === kind);
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
}
