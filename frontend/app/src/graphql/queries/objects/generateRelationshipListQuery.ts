import { RelationshipSchema } from "@/screens/schema/types";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

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
