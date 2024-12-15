import graphqlClient from "@/graphql/graphqlClientApollo";
import { generateRelationshipListQuery } from "@/graphql/queries/objects/generateRelationshipListQuery";
import { gql } from "@apollo/client";

export type getRelationshipsFromApiParams = {
  peer: string;
  limit?: number;
  offset?: number;
  search?: string;
  branchName: string;
  atDate: Date | null;
  parent?: { name: string; value: string };
};

export const getRelationshipsFromApi = async ({
  peer,
  limit,
  offset,
  search,
  branchName,
  atDate,
  parent,
}: getRelationshipsFromApiParams) => {
  const query = gql(generateRelationshipListQuery({ peer, limit, offset, search, parent }));

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
};
