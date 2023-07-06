import Handlebars from "handlebars";

export const getGroups = Handlebars.compile(`
query Group {
  {{#if kind}}
  {{kind}}(ids:["{{objectid}}"]) {
    edges {
      node {
        member_of_groups {
          count
          edges {
            node {
              id
              display_label
            }
          }
        }
      }
    }
  }
  {{/if}}
  CoreGroup{{#if filters}}({{{filters}}}){{/if}} {
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
