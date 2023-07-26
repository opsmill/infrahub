import Handlebars from "handlebars";

export const getProposedChangesFilesThreads = Handlebars.compile(`
query {
  {{kind}}{{#if id}}(change__id: "{{id}}"){{/if}} {
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

                file {
          value
        }

        commit {
          value
        }

        repository {
          node {
            id
          }
        }

        line_number {
          value
        }

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
