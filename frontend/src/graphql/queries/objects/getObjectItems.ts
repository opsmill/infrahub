import Handlebars from "handlebars";

export const getObjectItems = Handlebars.compile(`
query {{kind}} {
  {{name}}{{#if filterString}}({{{filterString}}}){{/if}} {
    id
    display_label
    {{#each attributes}}
      {{this.name}} {
          value
      }
    {{/each}}
    {{#each relationships}}
      {{this.name}} {
          display_label
      }
    {{/each}}
  }
}
`);

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
              display_label
          }
        {{/each}}
      }
    }
  }
}
`);
