import Handlebars from "handlebars";

export const getProposedChangesArtifactsThreads = Handlebars.compile(`
query {
  {{kind}}{{#if id}}(change__ids: "{{id}}"){{/if}} {
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

        line_number {
          value
        }

        storage_id {
          value
        }

        resolved {
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
