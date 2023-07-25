import Handlebars from "handlebars";

export const getProposedChangesFilesThreads = Handlebars.compile(`
query details {
  {{kind}}{{#if id}}(ids: ["{{id}}"]){{/if}} {
    count
    edges {
      node {
        id
        display_label
        __typename
        _updated_at

        {{#each attributes}}
          {{this.name}} {
              value
          }
        {{/each}}

        comments {
          edges {
            node {
              id
              text {
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
