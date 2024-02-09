import Handlebars from "handlebars";

export const getCheckDetails = Handlebars.compile(`
{
  CoreCheck(ids: ["{{id}}"]) {
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
        origin{
          value
        }
        created_at {
          value
        }
        ... on CoreDataCheck {
          conflicts {
            value
          }
          keep_branch {
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
`);
