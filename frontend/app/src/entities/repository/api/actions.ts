import { graphql } from "gql.tada";

export const CHECK_REPOSITORY_CONNECTIVITY = graphql(`
  mutation CHECK_REPOSITORY_CONNECTIVITY($repositoryId: String!) {
    InfrahubRepositoryConnectivity(data: { id: $repositoryId }) {
      ok
      message
    }
  }
`);
