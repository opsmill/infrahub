import { gql } from "@apollo/client";

export const CHECK_REPOSITORY_CONNECTIVITY = gql`
  mutation CHECK_REPOSITORY_CONNECTIVITY($repositoryId: String!) {
    InfrahubRepositoryConnectivity(data: { id: $repositoryId }) {
      message
      ok
    }
  }
`;

export const REIMPORT_LAST_COMMIT = gql`
  mutation REIMPORT_LAST_COMMIT($repositoryId: String!) {
    InfrahubRepositoryProcess(data: { id: $repositoryId }) {
      ok
    }
  }
`;
