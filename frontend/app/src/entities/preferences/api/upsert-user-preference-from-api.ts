import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const UPSERT_USER_PREFERENCE = graphql(`
  mutation UpsertUserPreference($dateFormat: DateFormat, $timezone: String) {
    InfrahubSetPreferences(scope: USER, date_format: $dateFormat, timezone: $timezone) {
      ok
      date_format
      timezone
    }
  }
`);

export type UpsertUserPreferenceVariables = VariablesOf<typeof UPSERT_USER_PREFERENCE>;

export function upsertUserPreferenceFromApi(variables: UpsertUserPreferenceVariables) {
  return graphqlClient.mutate({ mutation: UPSERT_USER_PREFERENCE, variables });
}
