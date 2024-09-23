import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { RelationshipSchema } from "@/screens/schema/types";

export const generateRelationshipListQuery = ({
  relationshipSchema,
}: {
  relationshipSchema: RelationshipSchema;
  search?: string;
}): string => {
  const request = {
    query: {
      __name: "GetRelationshipList",
      [relationshipSchema.peer]: {
        edges: {
          node: {
            id: true,
            display_label: true,
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};
