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
`);
