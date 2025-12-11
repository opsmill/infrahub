import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

import { BRANCH_DELETE } from "@/entities/branches/api/deleteBranch";

export type DeleteBranchParams = {
  name: string;
};

export type DeleteBranch = (params: DeleteBranchParams) => Promise<boolean>;

export const deleteBranch: DeleteBranch = async ({ name }) => {
  const { data, errors } = await graphqlClient.mutate({
    mutation: BRANCH_DELETE,
    variables: { name },
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data?.BranchDelete?.ok ?? false;
};
