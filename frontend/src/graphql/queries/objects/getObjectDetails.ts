import Handlebars from "handlebars";
import "../../../utils/handlebars"; // Import handlebars utils

export const getObjectDetailsPaginated = Handlebars.compile(`
query {{kind}} {
  {{kind}} (ids: ["{{objectid}}"]) {
    edges {
      node {
        id
        display_label

        {{#each attributes}}
          {{this.name}} {
              value
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
              {{#if (eq this.kind "Dropdown")}}
              color
              description
              {{/if}}
          }
          {{/each}}

          {{#each relationships}}
            {{this.name}}{{#if this.paginated}}(limit: 100){{/if}} {
              {{#if this.paginated}}
                edges {
              {{/if}}
                node {
                  id
                  display_label
                  __typename
                }
                properties {
                  updated_at
                  is_protected
                  is_visible
                  source {
                    id
                    display_label
                    __typename
                  }
                  owner {
                    id
                    display_label
                    __typename
                  }
                  __typename
                }
              {{#if this.paginated}}
              }
              {{/if}}
            }
        {{/each}}

        {{#each relationshipsTabs}}
          {{this.name}}(limit: 100) {
            count
          }
        {{/each}}
      }
    }
  }
}
`);
