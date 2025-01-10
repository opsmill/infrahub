import { IProfileSchema, iNodeSchema } from "@/screens/schema/schema.atom";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/shared/api/graphql/utils";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

export const generateObjectEditFormQuery = ({
  schema,
  objectId,
}: {
  schema: iNodeSchema | IProfileSchema;
  objectId: string;
}): string => {
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
            ...addAttributesToRequest(schema.attributes ?? [], { withPermissions: true }),
            ...addRelationshipsToRequest(getRelationshipsForForm(schema.relationships ?? [], true)),
            ...("generate_profile" in schema && schema.generate_profile
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
