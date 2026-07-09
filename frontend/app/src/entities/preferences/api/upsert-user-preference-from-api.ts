import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

// `scope: USER` writes the caller's OWN row. Passing an explicit `null` for a
// field resets it (clearing the personal override so the field falls back to the
// org default); omitting the variable leaves the stored value unchanged.
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
  /**
   * The caller's own override for `date_format`. Explicit `null` resets it to
   * the global default. Omitting the key leaves the stored value unchanged.
   */
  dateFormat?: string | null;
  /** As `dateFormat`, for `timezone`. */
  timezone?: string | null;
}

/**
 * Upsert the caller's OWN preference row (IFC-2720). The mutation never carries
 * an account argument — the backend resolves the calling account from the
 * session and lazily creates the row on first write. Passing explicit `null`
 * for a field resets it to the global default; omitting a field leaves it
 * unchanged.
 */
export async function upsertUserPreferenceFromApi(params: UpsertUserPreferenceFromApiParams) {
  // The date-format dropdown constrains values to the DateFormat enum keys; the domain layer
  // carries date_format as a plain string, so narrow it to the generated variable type here at the
  // GraphQL boundary (only these keys ever reach this function).
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

  // Apollo resolves even when the mutation reports an application-level failure without GraphQL
  // errors, so assert the payload's `ok` flag — otherwise a failed save would run the caller's
  // success path (toast + cache invalidation) as if it had worked.
  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to save your preferences");
  }

  return result;
}
