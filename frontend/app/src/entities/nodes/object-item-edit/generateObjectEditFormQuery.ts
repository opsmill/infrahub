import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";

import { getSchema } from "@/entities/schema/domain/get-schema";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

export const generateObjectEditFormQuery = ({
  schema,
  objectId,
}: {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
}): string => {
  let objectSchema = schema;
  if (isTemplateSchema(schema)) {
    const { schema: nodeSchemaOfTemplate } = getSchema(schema.name);
    if (nodeSchemaOfTemplate) {
      objectSchema = nodeSchemaOfTemplate;
    }
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
            ...("generate_profile" in objectSchema && objectSchema.generate_profile
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
