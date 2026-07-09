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
  /** Org default for `date_format`. Explicit `null` clears it; omitting the key leaves it unchanged. */
  dateFormat?: string | null;
  /** As `dateFormat`, for `timezone`. */
  timezone?: string | null;
}

/**
 * Update the org-wide singleton (no id argument; the resolver lazily materialises the row).
 * Explicit `null` clears a field; omitting it leaves the stored value unchanged.
 */
export async function updateGlobalPreferenceFromApi(params: UpdateGlobalPreferenceFromApiParams) {
  // date_format is a plain string in the domain but constrained to DateFormat enum keys by the UI,
  // so narrow it to the generated variable type here at the GraphQL boundary.
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

  // Apollo resolves on application-level failures that carry no GraphQL errors, so assert `ok`;
  // otherwise a failed update would run the caller's success path (toast + cache invalidation).
  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to update the organisation defaults");
  }

  return result;
}
