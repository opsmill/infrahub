import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";

import { getSchema } from "@/entities/schema/domain/get-schema";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

export const generateObjectEditFormQuery = ({
  schema,
  objectId,
  extraRelationshipNames = [],
}: {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
  extraRelationshipNames?: string[];
}): string => {
  let objectSchema = schema;
  if (isTemplateSchema(schema)) {
    const { schema: nodeSchemaOfTemplate } = getSchema(schema.name);
    if (nodeSchemaOfTemplate) {
      objectSchema = nodeSchemaOfTemplate;
    }
  }

  const formRelationships = getRelationshipsForForm(schema, true);
  const extraRelationships = (schema.relationships ?? []).filter(
    (r) =>
      extraRelationshipNames.includes(r.name) && !formRelationships.some((fr) => fr.name === r.name)
  );

  const request = {
    query: {
      __name: "GetObjectForEditForm",
      [schema.kind as string]: {
        __args: {
          ids: [objectId],
        },
        edges: {
          node: {
            ...nodeCoreFragment,
            ...addAttributesToRequest(schema.attributes ?? [], {
              withMetadata: true,
              withPermissions: true,
            }),
            ...addRelationshipsToRequest([...formRelationships, ...extraRelationships], {
              withMetadata: true,
            }),
            ...("generate_profile" in objectSchema && objectSchema.generate_profile
              ? {
                  profiles: {
                    edges: {
                      node: {
                        ...nodeCoreFragment,
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
