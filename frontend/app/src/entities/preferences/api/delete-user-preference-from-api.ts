import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const DELETE_USER_PREFERENCE = graphql(`
  mutation DeleteUserPreference($id: String!) {
    CoreUserPreferenceDelete(data: { id: $id }) {
      ok
    }
  }
`);

export interface DeleteUserPreferenceFromApiParams {
  id: string;
}

export function deleteUserPreferenceFromApi({ id }: DeleteUserPreferenceFromApiParams) {
  return graphqlClient.mutate({
    mutation: DELETE_USER_PREFERENCE,
    variables: { id },
  });
}
