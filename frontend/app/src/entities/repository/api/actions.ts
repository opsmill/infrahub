import { graphql } from "gql.tada";

export const CHECK_REPOSITORY_CONNECTIVITY = graphql(`
  mutation CHECK_REPOSITORY_CONNECTIVITY($repositoryId: String!) {
    InfrahubRepositoryConnectivity(data: { id: $repositoryId }) {
      message
      ok
    }
  }
`);

export const REIMPORT_LAST_COMMIT = graphql(`
  mutation REIMPORT_LAST_COMMIT($repositoryId: String!) {
    InfrahubRepositoryProcess(data: { id: $repositoryId }) {
      ok
    }
  }
`);
