import Handlebars from "@/shared/libs/handlebars";

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
            node_metadata {
              created_at
              created_by {
                display_label
              }
            }
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
