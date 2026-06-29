import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const UPSERT_USER_PREFERENCE = graphql(`
  mutation UpsertUserPreference($dateFormat: String, $timezone: String) {
    InfrahubUserPreferenceUpsert(date_format: $dateFormat, timezone: $timezone) {
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
export function upsertUserPreferenceFromApi(params: UpsertUserPreferenceFromApiParams) {
  const variables: { dateFormat?: string | null; timezone?: string | null } = {};
  if ("dateFormat" in params) variables.dateFormat = params.dateFormat;
  if ("timezone" in params) variables.timezone = params.timezone;

  return graphqlClient.mutate({
    mutation: UPSERT_USER_PREFERENCE,
    variables,
  });
}
