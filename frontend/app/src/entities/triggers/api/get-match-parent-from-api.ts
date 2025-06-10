import { NODE_TRIGGER_RULE } from "@/entities/triggers/constants";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

const GET_MATCH_PARENT = gql`
query GetMatchParent($objectsId: [ID]) {
  [${NODE_TRIGGER_RULE}]: {
    __args: {
      matches__ids: $objectsId,
      },
      edges: {
        node: {
          id
          node_kind: {
            value
          }
        }
      }
    }
  }
}
`;

export interface GetMatchParentParams extends ContextParams {
  objectId: string;
}

export const getMatchParentFromApi = async ({
  branchName,
  atDate,
  objectId,
}: GetMatchParentParams) => {
  return graphqlClient.query({
    query: GET_MATCH_PARENT,
    variables: {
      objectsId: [objectId],
    },
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
