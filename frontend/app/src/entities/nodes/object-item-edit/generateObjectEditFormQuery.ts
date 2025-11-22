import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";

import { getSchema } from "@/entities/schema/domain/get-schema";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";

export const generateObjectEditFormQuery = ({
  schema,
  objectId,
}: {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
}): string => {
  let parentSchema: NodeSchema | ProfileSchema | undefined;
  if (schema.kind && schema.kind.includes("Template")) {
    parentSchema = getSchema(schema.name).schema;
  }
  const request = {
    query: {
      __name: "GetObjectForEditForm",
      [schema.kind as string]: {
        __args: {
          ids: [objectId],
        },
        edges: {
          node: {
            id: true,
            hfid: true,
            display_label: true,
            ...addAttributesToRequest(schema.attributes ?? [], {
              withMetadata: true,
              withPermissions: true,
            }),
            ...addRelationshipsToRequest(
              getRelationshipsForForm(schema.relationships ?? [], true, schema),
              { withMetadata: true }
            ),
            ...(("generate_profile" in schema && schema.generate_profile) ||
            (parentSchema && "generate_profile" in parentSchema && parentSchema.generate_profile)
              ? {
                  profiles: {
                    edges: {
                      node: {
                        display_label: true,
                        id: true,
                        profile_priority: {
                          value: true,
                        },
                      },
                    },
                  },
                }
              : undefined),
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
