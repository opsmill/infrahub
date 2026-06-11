import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const UPDATE_GLOBAL_PREFERENCE = graphql(`
  mutation UpdateGlobalPreference($data: CoreGlobalPreferenceUpdateInput!) {
    CoreGlobalPreferenceUpdate(data: $data) {
      ok
      object {
        id
      }
    }
  }
`);

export interface UpdateGlobalPreferenceFromApiParams {
  id: string;
  dateFormat: string | null;
  timezone: string | null;
}

export function updateGlobalPreferenceFromApi({
  id,
  dateFormat,
  timezone,
}: UpdateGlobalPreferenceFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPDATE_GLOBAL_PREFERENCE,
    variables: {
      data: {
        id,
        date_format: { value: dateFormat },
        timezone: { value: timezone },
      },
    },
  });
}
