import "@/utils/handlebars"; // Import handlebars utils
import Handlebars from "handlebars";

export const getObjectItemsPaginated = Handlebars.compile(`
query {{kind}} (
  $offset: Int
  $limit: Int
) {
  {{kind}}(
    {{#if filters}}{{{filters}}}{{/if}}
    offset: $offset
    limit: $limit
  ) {
    count
    edges {
      node {
        id
        display_label
        __typename

        {{#each attributes}}
          {{this.name}} {
              value
              {{#if (eq this.kind "Dropdown")}}
              color
              description
              label
              {{/if}}
          }
        {{/each}}

        {{#each relationships}}
          {{this.name}} {
            {{#if this.paginated}}
              edges {
            {{/if}}
              node {
                id
                display_label
              }
            {{#if this.paginated}}
              }
            {{/if}}
          }
        {{/each}}
      }
    }
    permissions{
      edges{
        node{
          kind
          view
          create
          update
          delete
        }
      }
    }
  }
}
`);
