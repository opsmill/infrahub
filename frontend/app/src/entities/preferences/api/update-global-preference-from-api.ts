import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const UPDATE_GLOBAL_PREFERENCE = graphql(`
  mutation UpdateGlobalPreference(
    $dateFormat: DateFormat
    $timezone: String
    $instanceLabel: String
    $instanceColor: InstanceColor
  ) {
    InfrahubSetPreferences(
      scope: GLOBAL
      date_format: $dateFormat
      timezone: $timezone
      instance_label: $instanceLabel
      instance_color: $instanceColor
    ) {
      ok
      date_format
      timezone
      instance_label
      instance_color
    }
  }
`);

export type UpdateGlobalPreferenceVariables = VariablesOf<typeof UPDATE_GLOBAL_PREFERENCE>;

export function updateGlobalPreferenceFromApi(variables: UpdateGlobalPreferenceVariables) {
  // A failed save is reported where the save is made, not by the client.
  return graphqlClient.mutate({
    mutation: UPDATE_GLOBAL_PREFERENCE,
    variables,
    context: { processErrorMessage: () => {} },
  });
}
