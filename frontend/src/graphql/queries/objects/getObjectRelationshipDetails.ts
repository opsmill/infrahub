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
                      display_label
                    }
                  {{#if this.paginated}}
                    }
                  {{/if}}
                }
              {{/each}}
            }
          }
        }
      }
    }
  }
}
`);
