import Handlebars from "@/shared/libs/handlebars";

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
