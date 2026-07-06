import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import type { ContextParams } from "@/shared/api/types";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";

import type { NodeSchema, ProfileSchema } from "@/entities/schema/domain/model/schema";
import { isTemplateSchema } from "@/entities/schema/domain/rules/is-template-schema";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

export interface GetObjectForEditingFromApiParams extends ContextParams {
  schema: NodeSchema | ProfileSchema;
  objectId: string;
  extraRelationshipNames?: string[];
}

export async function getObjectForEditingFromApi({
  schema,
  objectId,
  extraRelationshipNames = [],
  branchName,
  atDate,
}: GetObjectForEditingFromApiParams) {
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

  const queryString = jsonToGraphQLQuery({
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
  });

  return graphqlClient.query({
    query: gql(queryString),
    context: {
      branch: branchName,
      date: atDate,
    },
    fetchPolicy: "no-cache",
  });
}
