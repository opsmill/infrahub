import { jsonToGraphQLQuery } from "json-to-graphql-query";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { nodeCoreFragment } from "@/shared/api/graphql/fragments";
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
            // Only request `profiles` when the schema actually exposes it. The backend
            // adds a `profiles` relationship (peer CoreProfile) to any node OR generic
            // whose namespace is not restricted (Builtin excepted), which mirrors exactly
            // when the GraphQL type exposes the `profiles` field. Relying on the
            // relationship keeps us correct for both nodes and profile-having generics
            // (e.g. BuiltinIPAddress) while still omitting it for generics that lack it
            // (e.g. CoreGenericRepository in the restricted Core namespace).
            ...((objectSchema.relationships ?? []).some((rel) => rel.name === "profiles")
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
    query: graphql(queryString),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
