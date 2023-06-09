import Handlebars from "handlebars";

export const getObjectItemsPaginated = Handlebars.compile(`
query {{kind}} {
  {{name}}{{#if filters}}({{{filters}}}){{/if}} {
    count
    edges {
      node {
        id
        display_label

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
