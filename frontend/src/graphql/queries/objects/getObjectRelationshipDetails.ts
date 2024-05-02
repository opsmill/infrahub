import Handlebars from "handlebars";

export const getObjectRelationshipsDetailsPaginated = Handlebars.compile(`
query GetObjectRelationships_{{kind}} {
  {{kind}} (ids: ["{{objectid}}"]) {
    count
    edges {
      node {
        {{relationship}}{{#if filters}}({{{filters}}}){{/if}} {
          count
          edges {
            node {
              id
              display_label
              __typename

              {{#each columns}}

              {{#if this.isAttribute}}

              {{this.name}} {
                value
                {{#if (eq this.kind "Dropdown")}}
                color
                description
                label
                {{/if}}
              }

              {{/if}}

              {{#if this.isRelationship}}

              {{this.name}} {
                {{#if this.paginated}}
                  edges {
                {{/if}}
                  node {
                    display_label
                  }
                {{#if this.paginated}}
                  }
                {{/if}}
              }

              {{/if}}

              {{/each}}
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
            }
          }
        }
      }
    }
  }
}
`);
