import { getObjectPermissionsQuery } from "@/entities/permission/queries/getObjectPermissions";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

export type GetPermissionsFromApiParams = {
  kind: string;
  branchName?: string | null;
  atDate?: Date | null;
};

export const getPermissionsFromApi = ({
  kind,
  branchName,
  atDate,
}: GetPermissionsFromApiParams) => {
  const query = gql(getObjectPermissionsQuery(kind));
  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
