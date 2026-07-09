import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// `scope: GLOBAL` writes the org-wide defaults row. Server-gated on
// `manage_global_preferences`.
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
  /** The org default for `date_format`. Explicit `null` clears it. Omitting the key leaves it unchanged. */
  dateFormat?: string | null;
  /** As `dateFormat`, for `timezone`. */
  timezone?: string | null;
}

/**
 * Update the organisation-wide singleton (IFC-2720). Backend-gated on
 * `manage_global_preferences`; there is no id argument (the row is a singleton
 * lazily materialised by the resolver). Passing explicit `null` for a field clears
 * it; omitting a field leaves the stored value unchanged.
 */
export async function updateGlobalPreferenceFromApi(params: UpdateGlobalPreferenceFromApiParams) {
  // The date-format dropdown constrains values to the DateFormat enum keys; the domain layer
  // carries date_format as a plain string, so narrow it to the generated variable type here at the
  // GraphQL boundary (only these keys ever reach this function).
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

  // Apollo resolves even when the mutation reports an application-level failure without GraphQL
  // errors, so assert the payload's `ok` flag — otherwise a failed update would run the caller's
  // success path (toast + cache invalidation) as if it had worked.
  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to update the organisation defaults");
  }

  return result;
}
