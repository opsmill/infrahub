import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const UPDATE_GLOBAL_PREFERENCE = graphql(`
  mutation UpdateGlobalPreference($dateFormat: DateFormat, $timezone: String) {
    InfrahubSetPreferences(scope: GLOBAL, date_format: $dateFormat, timezone: $timezone) {
      ok
      date_format
      timezone
    }
  }
`);

export type UpdateGlobalPreferenceVariables = VariablesOf<typeof UPDATE_GLOBAL_PREFERENCE>;

export function updateGlobalPreferenceFromApi(variables: UpdateGlobalPreferenceVariables) {
  return graphqlClient.mutate({ mutation: UPDATE_GLOBAL_PREFERENCE, variables });
}
