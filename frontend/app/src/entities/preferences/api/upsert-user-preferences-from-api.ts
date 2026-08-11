import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const UPSERT_USER_PREFERENCE = graphql(`
  mutation UpsertUserPreference($dateFormat: DateFormat, $timezone: String) {
    InfrahubSetPreferences(scope: USER, date_format: $dateFormat, timezone: $timezone) {
      ok
      date_format
      timezone
    }
  }
`);

export type UpsertUserPreferencesFromApiParams = VariablesOf<typeof UPSERT_USER_PREFERENCE>;

export function upsertUserPreferencesFromApi(variables: UpsertUserPreferencesFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPSERT_USER_PREFERENCE,
    variables,
    context: {
      processErrorMessage: () => {},
    },
  });
}
