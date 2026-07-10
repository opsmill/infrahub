import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// `scope: GLOBAL` writes the org-wide defaults row. Server-gated on `manage_global_preferences`.
const UPDATE_GLOBAL_PREFERENCE = graphql(`
  mutation UpdateGlobalPreference($dateFormat: DateFormat, $timezone: String) {
    InfrahubSetPreferences(scope: GLOBAL, date_format: $dateFormat, timezone: $timezone) {
      ok
      date_format
      timezone
    }
  }
`);

export interface UpdateGlobalPreferenceFromApiParams {
  /** Explicit `null` clears the field; omitting the key leaves it unchanged. */
  dateFormat?: string | null;
  timezone?: string | null;
}

export async function updateGlobalPreferenceFromApi(params: UpdateGlobalPreferenceFromApiParams) {
  // date_format is a plain string in the domain; narrow to the generated DateFormat enum type at the GraphQL boundary.
  const variables: VariablesOf<typeof UPDATE_GLOBAL_PREFERENCE> = {};
  if ("dateFormat" in params) {
    variables.dateFormat = params.dateFormat as VariablesOf<
      typeof UPDATE_GLOBAL_PREFERENCE
    >["dateFormat"];
  }
  if ("timezone" in params) variables.timezone = params.timezone;

  const result = await graphqlClient.mutate({
    mutation: UPDATE_GLOBAL_PREFERENCE,
    variables,
  });

  // Apollo resolves on application-level failures that carry no GraphQL errors, so assert `ok`.
  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to update the organisation defaults");
  }

  return result;
}
