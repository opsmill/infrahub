import Handlebars from "handlebars";

export const getProposedChangesChecks = Handlebars.compile(`
query {
  {{kind}}{{#if id}}(ids: ["{{id}}"]){{/if}} {
    edges {
      node {
        validations {
          count
          edges {
            node {
              state {
                value
              }
            }
          }
        }
      }
    }
  }
}
`);
