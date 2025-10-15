import type {
  GenericSchema,
  NodeSchema,
  ProfileSchema,
  TemplateSchema,
} from "@/entities/schema/types";

export type SchemaResult =
  | {
      schema: NodeSchema;
      isGeneric: false;
      isNode: true;
      isProfile: false;
      isTemplate: false;
    }
  | {
      schema: GenericSchema;
      isGeneric: true;
      isNode: false;
      isProfile: false;
      isTemplate: false;
    }
  | {
      schema: ProfileSchema;
      isGeneric: false;
      isNode: false;
      isProfile: true;
      isTemplate: false;
    }
  | {
      schema: TemplateSchema;
      isGeneric: false;
      isNode: false;
      isProfile: false;
      isTemplate: true;
    }
  | {
      schema: null;
      isGeneric: false;
      isNode: false;
      isProfile: false;
      isTemplate: false;
    };

export function resolveSchema(
  kind: string | null | undefined,
  schemas: {
    nodeSchemas: NodeSchema[];
    genericSchemas: GenericSchema[];
    profileSchemas: ProfileSchema[];
    templateSchemas: TemplateSchema[];
  }
): SchemaResult {
  if (!kind) {
    return {
      schema: null,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    };
  }

  const node = schemas.nodeSchemas.find((schema) => schema.kind === kind);
  if (node) {
    return {
      schema: node,
      isGeneric: false,
      isNode: true,
      isProfile: false,
      isTemplate: false,
    };
  }

  const generic = schemas.genericSchemas.find((schema) => schema.kind === kind);
  if (generic) {
    return {
      schema: generic,
      isGeneric: true,
      isNode: false,
      isProfile: false,
      isTemplate: false,
    };
  }

  const profile = schemas.profileSchemas.find((schema) => schema.kind === kind);
  if (profile) {
    return {
      schema: profile,
      isGeneric: false,
      isNode: false,
      isProfile: true,
      isTemplate: false,
    };
  }

  const template = schemas.templateSchemas.find((schema) => schema.kind === kind);
  if (template) {
    return {
      schema: template,
      isGeneric: false,
      isNode: false,
      isProfile: false,
      isTemplate: true,
    };
  }

  return {
    schema: null,
    isGeneric: false,
    isNode: false,
    isProfile: false,
    isTemplate: false,
  };
}
