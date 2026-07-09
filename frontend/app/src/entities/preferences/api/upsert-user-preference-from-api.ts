import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// `scope: USER` writes the caller's OWN row. Explicit `null` clears the personal override
// (field falls back to the org default); omitting the variable leaves the stored value unchanged.
const UPSERT_USER_PREFERENCE = graphql(`
  mutation UpsertUserPreference($dateFormat: DateFormat, $timezone: String) {
    InfrahubSetPreferences(scope: USER, date_format: $dateFormat, timezone: $timezone) {
      ok
      date_format
      timezone
    }
  }
`);

export interface UpsertUserPreferenceFromApiParams {
  /** Caller's override for `date_format`. Explicit `null` resets to the global default; omitting leaves unchanged. */
  dateFormat?: string | null;
  /** As `dateFormat`, for `timezone`. */
  timezone?: string | null;
}

/**
 * Upsert the caller's OWN preference row. No account argument: the backend resolves the account
 * from the session and lazily creates the row. Explicit `null` resets to the global default;
 * omitting a field leaves it unchanged.
 */
export async function upsertUserPreferenceFromApi(params: UpsertUserPreferenceFromApiParams) {
  // date_format is a plain string in the domain but constrained to DateFormat enum keys by the UI,
  // so narrow it to the generated variable type here at the GraphQL boundary.
  const variables: VariablesOf<typeof UPSERT_USER_PREFERENCE> = {};
  if ("dateFormat" in params) {
    variables.dateFormat = params.dateFormat as VariablesOf<
      typeof UPSERT_USER_PREFERENCE
    >["dateFormat"];
  }
  if ("timezone" in params) variables.timezone = params.timezone;

  const result = await graphqlClient.mutate({
    mutation: UPSERT_USER_PREFERENCE,
    variables,
  });

  // Apollo resolves on application-level failures that carry no GraphQL errors, so assert `ok`;
  // otherwise a failed save would run the caller's success path (toast + cache invalidation).
  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to save your preferences");
  }

  return result;
}
