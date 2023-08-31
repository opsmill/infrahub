import Handlebars from "handlebars";

export const getValidatorDetails = Handlebars.compile(`
query {
  CoreValidator(
    ids: ["{{id}}"]
  ) {
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
        checks {
          count
          edges {
            node {
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
              ... on CoreDataCheck {
                paths {
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
            }
          }
        }
      }
    }
  }
}

`);
