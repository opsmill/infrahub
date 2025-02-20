import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

const getDisplayLabelQuery = ({
  objectid,
  kind,
}: {
  objectid?: string;
  kind: string;
}) => {
  const request = {
    query: {
      __name: "GET_DISPLAY_LABEL",
      [kind]: {
        __args: {
          ids: [objectid],
        },
        edges: {
          node: {
            display_label: true,
          },
        },
      },
    },
  };

  return jsonToGraphQLQuery(request);
};

export function getDisplayLabelFromApi({
  objectid,
  kind,
  branchName,
  atDate,
}: {
  objectid?: string;
  kind: string;
  branchName: string;
  atDate: Date | null;
}) {
  return graphqlClient.query({
    query: gql(getDisplayLabelQuery({ objectid, kind })),
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
