import Handlebars from "handlebars";

export const getObjectRelationshipsDetailsPaginated = Handlebars.compile(`query {{kind}} {
  {{kind}} (ids: ["{{objectid}}"]) {
    edges {
      node {
        {{relationship}}{{#if filters}}({{{filters}}}){{/if}} {
          count
          edges {
            node {
              id
              display_label
              {{#each columns}}
              {{this.name}} {
                value
                {{#if (eq this.kind "Dropdown")}}
                  color
                  description
                  label
                {{/if}}
              }
              {{/each}}
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
            }
          }
        }
      }
    }
  }
}
`);
