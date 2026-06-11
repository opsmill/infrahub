import { graphql } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const UPSERT_USER_PREFERENCE = graphql(`
  mutation UpsertUserPreference($data: CoreUserPreferenceUpsertInput!) {
    CoreUserPreferenceUpsert(data: $data) {
      ok
      object {
        id
      }
    }
  }
`);

export interface UpsertUserPreferenceFromApiParams {
  accountId: string;
  dateFormat: string | null;
  timezone: string | null;
}

/**
 * Lazy upsert (IFC-2720): the payload never carries an id — the backend
 * resolves the calling account's existing row (or creates it on first save)
 * from the `account` relationship.
 */
export function upsertUserPreferenceFromApi({
  accountId,
  dateFormat,
  timezone,
}: UpsertUserPreferenceFromApiParams) {
  return graphqlClient.mutate({
    mutation: UPSERT_USER_PREFERENCE,
    variables: {
      data: {
        account: { id: accountId },
        date_format: { value: dateFormat },
        timezone: { value: timezone },
      },
    },
  });
}
