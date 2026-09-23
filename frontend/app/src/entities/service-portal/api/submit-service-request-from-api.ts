import { graphql, graphqlClient, type VariablesOf } from "@/shared/api/graphql/client";

const SUBMIT_SERVICE_REQUEST = graphql(`
  mutation ServiceRequestSubmit($entryId: String!, $inputs: GenericScalar!) {
    ServiceRequestSubmit(data: { entry_id: $entryId, inputs: $inputs }) {
      ok
      request {
        id
      }
    }
  }
`);

export type SubmitServiceRequestFromApiParams = VariablesOf<typeof SUBMIT_SERVICE_REQUEST>;

// No branch in the context: requests are always submitted against the default branch.
export const submitServiceRequestFromApi = async (variables: SubmitServiceRequestFromApiParams) => {
  return graphqlClient.mutate({
    mutation: SUBMIT_SERVICE_REQUEST,
    variables,
    // Validation errors are shown on the order form, not as a toast.
    context: { processErrorMessage: () => {} },
  });
};
