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
  dateFormat: string | null;
  timezone: string | null;
}

/**
 * Update the organisation-wide singleton (IFC-2720). Backend-gated on
 * `manage_global_preferences`; there is no id argument (the row is a singleton
 * lazily materialised by the resolver).
 */
export function updateGlobalPreferenceFromApi({
  dateFormat,
  timezone,
}: UpdateGlobalPreferenceFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPDATE_GLOBAL_PREFERENCE,
    variables: {
      // date_format is one of the DateFormat enum keys (dropdown-constrained); narrow from string.
      dateFormat: dateFormat as VariablesOf<typeof UPDATE_GLOBAL_PREFERENCE>["dateFormat"],
      timezone,
    },
  });
}
