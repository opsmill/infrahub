import { graphql, type VariablesOf } from "gql.tada";

import type { DateFormat } from "@/shared/api/graphql/generated/types";
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
  /** Explicit `null` resets the field to the global default; omitting leaves it unchanged. */
  dateFormat?: DateFormat | null;
  timezone?: string | null;
}

export async function upsertUserPreferenceFromApi(params: UpsertUserPreferenceFromApiParams) {
  const variables: VariablesOf<typeof UPSERT_USER_PREFERENCE> = {};
  if ("dateFormat" in params) variables.dateFormat = params.dateFormat;
  if ("timezone" in params) variables.timezone = params.timezone;

  const result = await graphqlClient.mutate({
    mutation: UPSERT_USER_PREFERENCE,
    variables,
  });

  // Apollo resolves on application-level failures that carry no GraphQL errors, so assert `ok`.
  if (!result.data?.InfrahubSetPreferences?.ok) {
    throw new Error("Failed to save your preferences");
  }

  return result;
}
