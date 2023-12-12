import Handlebars from "handlebars";

export const getProposedChangesFilesThreads = Handlebars.compile(`
query {
  {{kind}}{{#if id}}(change__ids: "{{id}}"){{/if}} {
    count
    edges {
      node {
        id
        display_label
        resolved {
          value
        }
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

              created_by {
                node {
                  display_label
                }
              }

              created_at {
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
