import { graphql } from "gql.tada";

export const CHECK_REPOSITORY_CONNECTIVITY = graphql(`
  mutation CHECK_REPOSITORY_CONNECTIVITY($repositoryId: String!) {
    InfrahubRepositoryConnectivity(data: { id: $repositoryId }) {
      ok
      message
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

export const IMPORT_READONLY_REPOSITORY_LAST_COMMIT = graphql(`
  mutation InfrahubReadOnlyRepositoryImportLastCommit($id: String!) {
    InfrahubReadOnlyRepositoryImportLastCommit(data: { id: $id }) {
      ok
    }
  }
`);
