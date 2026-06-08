import { graphql } from "gql.tada";

export const GET_VALIDATOR_DETAILS = graphql(`
  query GET_VALIDATOR_DETAILS($ids: [ID!], $checksOffset: Int, $checksLimit: Int) {
    CoreValidator(ids: $ids) {
      edges {
        node {
          id
          display_label
          conclusion {
            value
          }
          started_at {
            value
          }
          completed_at {
            value
          }
          state {
            value
          }
          ... on CoreRepositoryValidator {
            repository {
              node {
                display_label
              }
            }
          }
          ... on CoreArtifactValidator {
            definition {
              node {
                display_label
                name {
                  value
                }
                description {
                  value
                }
              }
            }
          }
          checks(offset: $checksOffset, limit: $checksLimit) {
            count
            edges {
              node {
                id
                display_label
                name {
                  value
                }
                message {
                  value
                }
                severity {
                  value
                }
                conclusion {
                  value
                }
                kind {
                  value
                }
                origin {
                  value
                }
                created_at {
                  value
                }
                ... on CoreDataCheck {
                  conflicts {
                    value
                  }
                }
                ... on CoreSchemaCheck {
                  conflicts {
                    value
                  }
                }
                ... on CoreFileCheck {
                  files {
                    value
                  }
                  commit {
                    value
                  }
                }
                ... on CoreArtifactCheck {
                  storage_id {
                    value
                  }
                  artifact_id {
                    value
                  }
                }
                __typename
              }
            }
          }
        }
      }
    }
  }
`);
