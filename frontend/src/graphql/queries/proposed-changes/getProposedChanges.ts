import Handlebars from "handlebars";

export const getProposedChanges = Handlebars.compile(`
query {
  {{kind}}{{#if id}}(ids: ["{{id}}"]){{/if}} {
    count
    edges {
      node {
        id
        display_label
        __typename
        _updated_at

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
                id
                display_label
              }
            {{#if this.paginated}}
              }
            {{/if}}
          }
        {{/each}}

        created_by {
          node {
            id
            display_label
          }
        }
      }
    }
  }

  {{#if accountKind}}

  {{accountKind}} {
    edges {
      node {
        id
        display_label
      }
    }
  }

  {{/if}}

  {{#if taskKind}}

  {{taskKind}}(related_node__ids: ["{{id}}"]) {
    count
  }

  {{/if}}
}
`);
