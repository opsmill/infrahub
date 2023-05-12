declare const Handlebars: any;

export const objectItems = Handlebars.compile(`
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
