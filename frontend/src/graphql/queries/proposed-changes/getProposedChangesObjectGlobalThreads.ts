import Handlebars from "handlebars";

export const getProposedChangesObjectGlobalThreads = Handlebars.compile(`
query {

  {{kind}}(
    change__ids: "{{id}}"
  ) {
    count
    edges {
      node {
        __typename
        id
        object_path {
          value
        }
        comments {
          count
        }
      }
    }
  }

{{#if conflicts}}

  CoreValidator(
    proposed_change__ids: ["{{id}}"]
  ) {
    edges {
      node {
        checks {
          edges {
            node {
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
              origin{
                value
              }
              created_at {
                value
              }
              ... on CoreDataCheck {
                paths {
                  value
                }
              }
              ... on CoreSchemaCheck {
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
              __typename
            }
          }
        }
      }
    }
  }

{{/if}}

}
`);
