import Handlebars from "handlebars";

export const getObjectDetailsAndPeers = Handlebars.compile(`
query {{kind.value}} {
  {{name}} (ids: ["{{objectid}}"]) {
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
          }
          {{/each}}
          {{#each relationships}}
            {{this.name}} {
                node {
                  id
                  display_label
                  __typename
                }
            }
        {{/each}}
      }
    }
  }
  {{#each peers}}
    {{this}} {
      edges {
        node {
          id
          display_label
        }
      }
    }
    {{/each}}
}
`);
