import Handlebars from "handlebars";

export const getGroups = Handlebars.compile(`
query GET_GROUPS {
  {{#if objectid}}
  {{kind}}(ids:["{{objectid}}"]) {
    edges {
      node {
        member_of_groups {
          count
          edges {
            node {
              id
              display_label
              description {
                value
              }
              members {
                count
              }
            }
          }
        }
      }
    }
  }
  {{/if}}

  {{groupKind}}{{#if filters}}({{{filters}}}){{/if}} {
    count
    edges {
      node {
        id
        display_label
        __typename

        {{#each attributes}}
          {{this.name}} {
              value
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
`);
