import Handlebars from "handlebars";

export const getThreadsAndChecks = Handlebars.compile(`
query getThreadsAndChecksFor{{kind}} {
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
              id
              ... on CoreDataCheck {
                conflicts {
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
