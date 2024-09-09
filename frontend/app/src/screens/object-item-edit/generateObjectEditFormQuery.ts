import { iNodeSchema, IProfileSchema } from "@/state/atoms/schema.atom";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { addAttributesToRequest, addRelationshipsToRequest } from "@/graphql/utils";
import { getRelationshipsForForm } from "@/components/form/utils/getRelationshipsForForm";

export const generateObjectEditFormQuery = ({
  schema,
  objectId,
  withProfiles,
}: {
  schema: iNodeSchema | IProfileSchema;
  objectId: string;
  withProfiles?: boolean;
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
            ...addAttributesToRequest(schema.attributes ?? []),
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
