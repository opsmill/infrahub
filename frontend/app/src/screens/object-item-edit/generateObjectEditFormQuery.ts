import { iNodeSchema, IProfileSchema } from "@/state/atoms/schema.atom";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/graphql/utils";
import { getRelationshipsForForm } from "@/components/form/utils/getRelationshipsForForm";

export const generateObjectEditFormQuery = (
  schema: iNodeSchema | IProfileSchema,
  objectId: string
): string => {
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
            display_label: true,
            ...addAttributesToRequest(schema.attributes ?? []),
            ...addRelationshipsToRequest(getRelationshipsForForm(schema.relationships ?? [], true)),
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
